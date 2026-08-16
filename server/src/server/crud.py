from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, func
from server.models import User, UserRole, SubjectClass, TokenBlacklist, Subject, Room, Schedule, Enrollment, \
    ClassStatus, TeachingAssignment, Exam, create_schedules_and_sessions, ExamStatus, ExamInvigilator
from server.rules import teaching_rule, exam_rule, subject_class_rule, enrollment_rule
from server.rules.enrollment_rule import MAXIMUM_CREDITS
from server.rules.exam_rule import check_exam_room_capacity
from server.rules.subject_class_rule import check_room_capacity
from server.schemas import UserCreate, SubjectClassCreate, EnrollmentCreate, TeachingAssignmentCreate, \
    SubjectClassUpdate, ExamCreate, ExamUpdate


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


def _generate_user_code(db: Session, role: UserRole) -> str:
    """Sinh mã user dạng SV230001 / GV230001 dựa theo role"""
    """Có thể race condition khi commit cùng lúc"""
    prefix = "SV" if role == UserRole.STUDENT else "GV" if role == UserRole.TEACHER else "AD"
    count = db.execute(
        select(func.count()).select_from(User).where(User.role == role)
    ).scalar_one()
    return f"{prefix}{count + 1:06d}"


def create_user(db: Session, user_data: UserCreate, avatar_url: str, max_retries: int = 3) -> User:
    for attempt in range(max_retries):
        try:
            user = User(
                user_code=_generate_user_code(db, UserRole.STUDENT),
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                avatar=avatar_url,
                email=user_data.email,
            )

            user.set_password(user_data.password)
            db.add(user)
            db.commit()
            db.refresh(user)
            return user
        except IntegrityError as e:
            db.rollback()
            msg = str(e.orig)
            if "user_code" in msg and attempt < max_retries - 1:
                continue
            if "email" in msg:
                raise HTTPException(400, "Email đã được sử dụng")
            raise
    raise RuntimeError("create_user: vượt quá số lần thử sinh user_code mà không thành công")


def blacklist_token(db: Session, jti: str, expires_at: datetime):
    entry = TokenBlacklist(jti=jti, expires_at=expires_at)
    db.add(entry)
    db.commit()


def is_token_blacklisted(db: Session, jti: str) -> bool:
    entry = db.query(TokenBlacklist).filter(TokenBlacklist.jti == jti).first()
    return entry is not None


def clear_expired_blacklist(db: Session):
    """Dọn các token blacklist đã hết hạn (gọi định kỳ hoặc mỗi lần logout)."""
    db.query(TokenBlacklist).filter(
        TokenBlacklist.expires_at < datetime.now(timezone.utc)
    ).delete()
    db.commit()


def get_all_subject(db: Session) -> list[Subject]:
    return db.scalars(select(Subject)).all()


def get_subject_by_id(db: Session, subject_id: int) -> bool:
    return db.scalar(select(Subject).where(Subject.id == subject_id))


def get_all_room(db: Session) -> list[Room]:
    return db.scalars(select(Room)).all()


def get_all_schedule(db: Session) -> list[Schedule]:
    return db.scalars(select(Schedule)).all()


def get_all_subject_class(db: Session) -> list[SubjectClass]:
    return db.scalars(select(SubjectClass).options(joinedload(SubjectClass.subject))).all()


def get_subject_class_by_subject(db: Session, subject_class_id: int) -> SubjectClass | None:
    return db.scalar(select(SubjectClass).where(SubjectClass.id == subject_class_id))


def _validate_schedules_or_raise(
        db: Session,
        schedules_data,
        max_students: int,
        semester,
        academic_year: str,
        exclude_subject_class_id: int | None = None,
) -> None:
    """Kiểm tra từng slot lịch học (phòng tồn tại, đủ sức chứa, không trùng lịch phòng)
    trước khi tạo/cập nhật SubjectClass."""
    for item in schedules_data:
        room = db.get(Room, item.room_id)
        if room is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Phòng học (id={item.room_id}) không tồn tại",
            )

        if not subject_class_rule.check_room_capacity(max_students, room.capacity):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sĩ số tối đa ({max_students}) vượt quá sức chứa phòng {room.name} ({room.capacity})",
            )

        if exam_rule.check_schedule_room_conflict(
                db,
                room_id=item.room_id,
                weekday=item.weekday,
                session_time=item.session,
                semester=semester,
                academic_year=academic_year,
                exclude_subject_class_id=exclude_subject_class_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Phòng {room.name} đã được xếp lịch trùng "
                       f"{item.weekday.value}/{item.session.value} trong học kỳ và năm học này.",
            )


def create_subject_class(db: Session, subject_class_data: SubjectClassCreate) -> tuple[SubjectClass, list[Schedule]]:
    subject = db.get(Subject, subject_class_data.subject_id)
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Môn học không tồn tại",
        )

    if not subject_class_rule.check_max_students_positive(subject_class_data.max_students):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sĩ số tối đa phải lớn hơn 0",
        )

    if not subject_class_rule.check_number_of_sessions_positive(subject_class_data.number_of_sessions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số buổi học phải lớn hơn 0",
        )

    _validate_schedules_or_raise(
        db,
        subject_class_data.schedules,
        subject_class_data.max_students,
        subject_class_data.semester,
        subject_class_data.academic_year,
    )

    subject_class = SubjectClass(
        subject_class_name=subject_class_data.subject_class_name,
        subject_id=subject_class_data.subject_id,
        semester=subject_class_data.semester,
        academic_year=subject_class_data.academic_year,
        start_date=subject_class_data.start_date,
        number_of_sessions=subject_class_data.number_of_sessions,
        status=ClassStatus.OPEN,
        max_students=subject_class_data.max_students,
    )
    db.add(subject_class)
    db.flush()

    # Chuyển đổi Pydantic schemas sang list[dict]
    schedule_data = [
        {
            "room_id": item.room_id,
            "weekday": item.weekday,
            "session": item.session,
        }
        for item in subject_class_data.schedules
    ]

    # Gọi hàm duy nhất để xử lý cả Schedule và ClassSession
    schedules = create_schedules_and_sessions(db, subject_class, schedule_data)

    db.commit()
    db.refresh(subject_class)
    for schedule in schedules:
        db.refresh(schedule)

    subject_class = db.scalar(
        select(SubjectClass).where(SubjectClass.id == subject_class.id).options(joinedload(SubjectClass.subject))
    )
    schedules = db.scalars(
        select(Schedule).where(Schedule.subject_class_id == subject_class.id).options(joinedload(Schedule.room))
    ).all()

    return subject_class, schedules


def update_subject_class(db: Session, subject_class_data: SubjectClassUpdate, subject_class_id: int) -> tuple[
    SubjectClass, list[Schedule]]:
    subject_class = db.scalar(
        select(SubjectClass).where(SubjectClass.id == subject_class_id).options(joinedload(SubjectClass.subject)))
    if subject_class is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lớp học phần không tồn tại")

    if not subject_class_rule.check_max_students_positive(subject_class_data.max_students):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sĩ số tối đa phải lớn hơn 0")

    if not subject_class_rule.check_number_of_sessions_positive(subject_class_data.number_of_sessions):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Số buổi học phải lớn hơn 0")

    _validate_schedules_or_raise(
        db,
        subject_class_data.schedules,
        subject_class_data.max_students,
        subject_class_data.semester,
        subject_class_data.academic_year,
        exclude_subject_class_id=subject_class_id,
    )

    subject_class.subject_class_name = subject_class_data.subject_class_name
    subject_class.semester = subject_class_data.semester
    subject_class.academic_year = subject_class_data.academic_year
    subject_class.start_date = subject_class_data.start_date
    subject_class.number_of_sessions = subject_class_data.number_of_sessions
    subject_class.max_students = subject_class_data.max_students
    subject_class.status = subject_class_data.status
    db.flush()

    # Xoá toàn bộ Schedule cũ của lớp (cascade xoá luôn ClassSession cũ) rồi tạo lại từ đầu
    old_schedules = db.scalars(select(Schedule).where(Schedule.subject_class_id == subject_class_id)).all()
    for old_schedule in old_schedules:
        db.delete(old_schedule)
    db.flush()

    # Chuyển đổi Pydantic schemas sang list[dict]
    schedule_data = [
        {
            "room_id": item.room_id,
            "weekday": item.weekday,
            "session": item.session,
        }
        for item in subject_class_data.schedules
    ]

    # Tạo lại Schedules và Sessions mới
    schedules = create_schedules_and_sessions(db, subject_class, schedule_data)

    db.commit()
    db.refresh(subject_class)
    for schedule in schedules:
        db.refresh(schedule)

    subject_class = db.scalar(
        select(SubjectClass).where(SubjectClass.id == subject_class.id).options(joinedload(SubjectClass.subject))
    )
    schedules = db.scalars(
        select(Schedule).where(Schedule.subject_class_id == subject_class.id).options(joinedload(Schedule.room))
    ).all()

    return subject_class, schedules


def get_teacher(db: Session) -> list[User]:
    return db.scalars(select(User).where(User.role == UserRole.TEACHER)).all()


def get_teaching_assignment_by_subject_class(db: Session, subject_class_id: int):
    subject_class = db.get(SubjectClass, subject_class_id)
    if subject_class is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lớp học phần không tồn tại."
        )
    return db.scalar(
        select(TeachingAssignment).where(TeachingAssignment.subject_class_id == subject_class_id)
    )


def create_teacher_assignment(db: Session, teaching_assignment_data: TeachingAssignmentCreate) -> TeachingAssignment:
    teacher = db.get(User, teaching_assignment_data.teacher_id)
    if teacher is None or teacher.role != UserRole.TEACHER:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy giảng viên."
        )

    subject_class = db.get(SubjectClass, teaching_assignment_data.subject_class_id)
    if subject_class is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy lớp học phần."
        )

    if teaching_rule.check_subject_class_has_teacher(db, teaching_assignment_data.subject_class_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lớp học phần này đã được phân công giảng viên rồi."
        )

    if teaching_rule.check_teacher_schedule_conflict(db, teaching_assignment_data.teacher_id,
                                                     teaching_assignment_data.subject_class_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Giảng viên bị trùng thời khóa biểu giảng dạy."
        )

    teaching_assignment = TeachingAssignment(
        teacher_id=teaching_assignment_data.teacher_id,
        subject_class_id=subject_class.id,
    )

    db.add(teaching_assignment)
    db.commit()
    db.refresh(teaching_assignment)
    return teaching_assignment


def update_teacher_assignment(db: Session, teaching_assignment_data: TeachingAssignmentCreate,
                              teaching_assignment_id: int) -> TeachingAssignment:
    teaching_assignment = db.get(TeachingAssignment, teaching_assignment_id)
    if teaching_assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phân công giảng dạy.")

    teacher = db.get(User, teaching_assignment_data.teacher_id)
    if teacher is None or teacher.role != UserRole.TEACHER:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy giảng viên.")

    subject_class = db.get(SubjectClass, teaching_assignment_data.subject_class_id)
    if subject_class is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lớp học phần.")

    if teaching_rule.check_subject_class_has_teacher(
            db, teaching_assignment_data.subject_class_id, exclude_assignment_id=teaching_assignment_id,
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Lớp học phần này đã được phân công giảng viên khác rồi.")

    if teaching_rule.check_teacher_schedule_conflict(
            db, teaching_assignment_data.teacher_id, teaching_assignment_data.subject_class_id,
            exclude_assignment_id=teaching_assignment_id,
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Giảng viên bị trùng thời khóa biểu giảng dạy.")

    teaching_assignment.teacher_id = teaching_assignment_data.teacher_id
    teaching_assignment.subject_class_id = teaching_assignment_data.subject_class_id

    db.commit()
    db.refresh(teaching_assignment)
    return teaching_assignment


def get_all_exam(db: Session) -> list[Exam]:
    return db.scalars(select(Exam)).all()


def create_exam(db: Session, exam_data: ExamCreate) -> Exam:
    subject_class = db.get(SubjectClass, exam_data.subject_class_id)
    if subject_class is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lớp học phần không tồn tại.")

    room = db.get(Room, exam_data.room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phòng thi không tồn tại.")

    if not check_room_capacity(subject_class.max_students, room.capacity):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phong được chọn không đủ chỗ cho lớp học phần thi."
        )


    if not exam_rule.check_exam_date_after_last_session(db, exam_data.subject_class_id, exam_data.exam_date):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ngày thi phải diễn ra SAU buổi học cuối cùng của lớp học phần.",
        )

        # 2. Kiểm tra ngày thi không được đụng lịch trình học của chính lớp đó (Option 2)
    if exam_rule.check_exam_conflict_with_regular_class(db, exam_data.subject_class_id, exam_data.exam_date):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ngày thi bị trùng với một buổi học thường kỳ của lớp học phần này.",
        )

    # Không xếp lịch thi trùng với buổi học thường (ClassSession) đang diễn ra trong phòng
    if exam_rule.check_room_used_by_class_session(db, exam_data.room_id, exam_data.exam_date):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phòng đang có lớp học thường vào ngày này, không thể xếp lịch thi.",
        )

    # Không trùng khung giờ với một kỳ thi khác đã xếp trong cùng phòng
    if exam_rule.check_exam_time_overlap(
            db, exam_data.room_id, exam_data.exam_date, exam_data.time_frame, exam_data.duration,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phòng đã có lịch thi khác trùng khung giờ này.",
        )

    exam = Exam(
        subject_class_id=exam_data.subject_class_id,
        room_id=exam_data.room_id,
        exam_date=exam_data.exam_date,
        type=exam_data.type,
        time_frame=exam_data.time_frame,
        duration=exam_data.duration,
        status=ExamStatus.SCHEDULED,
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return exam


# check invigilator với các exam khác
def update_exam(db: Session, exam_data: ExamUpdate, exam_id: int) -> Exam:
    exam = db.scalar(select(Exam).where(Exam.id == exam_id))
    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy buổi thi của lớp học phần này."
        )

    if not exam_rule.check_exam_status(exam):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Buổi thi này đã hoàn thành hoặc đã hủy."
        )

    room = db.get(Room, exam_data.room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phòng thi không tồn tại.")

    if not check_room_capacity(exam.subject_class.max_students, room.capacity):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phong được chọn không đủ chỗ cho lớp học phần thi."
        )

    if not exam_rule.check_exam_date_after_last_session(db, exam.subject_class_id, exam_data.exam_date):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ngày thi phải diễn ra SAU buổi học cuối cùng của lớp học phần.",
        )

        # 2. Kiểm tra ngày thi không được đụng lịch trình học của chính lớp đó (Option 2)
    if exam_rule.check_exam_conflict_with_regular_class(db, exam.subject_class_id, exam_data.exam_date):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ngày thi bị trùng với một buổi học thường kỳ của lớp học phần này.",
        )

    # Không xếp lịch thi trùng với buổi học thường (ClassSession) đang diễn ra trong phòng
    if exam_rule.check_room_used_by_class_session(db, exam_data.room_id, exam_data.exam_date):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phòng đang có lớp học thường vào ngày này, không thể xếp lịch thi.",
        )

    # Không trùng khung giờ với một kỳ thi khác đã xếp trong cùng phòng
    if exam_rule.check_exam_time_overlap(
            db, exam_data.room_id, exam_data.exam_date, exam_data.time_frame, exam_data.duration, exam_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phòng đã có lịch thi khác trùng khung giờ này.",
        )

    exam.room_id=exam_data.room_id
    exam.exam_date=exam_data.exam_date
    exam.type=exam_data.type
    exam.time_frame=exam_data.time_frame
    exam.duration=exam_data.duration
    exam.status=exam_data.status

    db.commit()
    db.refresh(exam)
    return exam


def create_enrollment(db: Session, student_id: int, data: EnrollmentCreate) -> Enrollment:
    # with_for_update() khóa dòng subject_class -> tránh 2 sinh viên cùng đăng ký
    # vượt sĩ số trong lúc race condition (chỉ nhả lock khi commit/rollback).
    subject_class = db.execute(
        select(SubjectClass)
        .where(SubjectClass.id == data.subject_class_id)
        .with_for_update()
    ).scalar_one_or_none()

    if subject_class is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lớp học phần không tồn tại.",
        )

    if not enrollment_rule.check_subject_class_status(subject_class):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lớp học phần không mở đăng ký (đã đóng hoặc đã kết thúc).",
        )

    if enrollment_rule.check_duplicate_enrollment(db, student_id, data.subject_class_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bạn đã đăng ký lớp học phần này rồi.",
        )

    if not enrollment_rule.check_subject_class_capacity(db, subject_class):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lớp học phần đã đủ sĩ số, không thể đăng ký thêm.",
        )

    if enrollment_rule.check_schedule_conflict(
            db, student_id, data.subject_class_id, subject_class.semester, subject_class.academic_year
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lịch học của lớp này bị trùng với một lớp bạn đã đăng ký trong học kỳ này.",
        )

    if not enrollment_rule.check_credit_limit(db, student_id, subject_class):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Đăng ký lớp này sẽ vượt quá giới hạn {MAXIMUM_CREDITS} tín chỉ trong học kỳ.",
        )

    enrollment = Enrollment(
        student_id=student_id,
        subject_class_id=data.subject_class_id,
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment
