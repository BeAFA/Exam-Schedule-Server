from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, func
from server.models import User, UserRole, SubjectClass, TokenBlacklist, Subject, Room, Schedule, \
    ClassStatus, TeachingAssignment, Exam, create_schedules_and_sessions, ExamStatus, ExamInvigilator
from server.rules import teaching_rule, exam_rule, subject_class_rule
from server.rules.subject_class_rule import check_room_capacity
from server.schemas import SubjectClassCreate, TeachingAssignmentCreate, \
    SubjectClassUpdate, ExamCreate, ExamUpdate


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


def blacklist_token(db: Session, jti: str, expires_at: datetime):
    entry = TokenBlacklist(jti=jti, expires_at=expires_at)
    db.add(entry)
    db.commit()


def is_token_blacklisted(db: Session, jti: str) -> bool:
    entry = db.query(TokenBlacklist).filter(TokenBlacklist.jti == jti).first()
    return entry is not None


def clear_expired_blacklist(db: Session):
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
                       f"{item.weekday.value}/{item.session.value} trong học kỳ của năm học này.",
            )


def create_subject_class(db: Session, subject_class_data: SubjectClassCreate) -> tuple[SubjectClass, list[Schedule]]:
    subject = db.get(Subject, subject_class_data.subject_id)
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Môn học không tồn tại",
        )

    if subject_class_rule.check_subject_class_identity_conflict(
            db, subject_class_data.subject_id, subject_class_data.subject_class_name,
            subject_class_data.semester, subject_class_data.academic_year,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Lớp học phần này đã tồn tại.",
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

    if subject_class_rule.check_subject_class_identity_conflict(
            db, subject_class.subject_id, subject_class_data.subject_class_name,
            subject_class_data.semester, subject_class_data.academic_year,
            exclude_subject_class_id=subject_class_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Lớp học phần với thông tin này đã tồn tại.",
        )

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


def change_subject_class_active(db: Session, ids: list[int]) -> list[SubjectClass]:
    subject_classes = db.scalars(select(SubjectClass).where(SubjectClass.id.in_(ids))).all()

    found_ids = {sc.id for sc in subject_classes}
    missing = set(ids) - found_ids
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Không tìm thấy lớp học phần với id: {sorted(missing)}")

    for subject_class in subject_classes:
        new_active = not subject_class.is_active

        # Chỉ chặn khi đang chuyển SANG xóa mềm (True -> False)
        if not new_active and subject_class.status == ClassStatus.FINISHED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Lớp học phần (id={subject_class.id}) đã hoàn thành (FINISHED), không thể xóa.",
            )

        subject_class.is_active = new_active

        # Khi xóa mềm lớp, cascade xóa mềm các buổi thi SCHEDULED liên quan
        if not new_active:
            for exam in subject_class.exams:
                if exam.is_active and exam.status != ExamStatus.FINISHED:
                    exam.is_active = False

    db.commit()
    for subject_class in subject_classes:
        db.refresh(subject_class)
    return subject_classes


def get_teacher(db: Session) -> list[User]:
    return db.scalars(select(User).where(User.role == UserRole.TEACHER)).all()


def get_teacher_by_id(db: Session, teacher_id: int) -> User:
    return db.scalar(select(User).where(User.role == UserRole.TEACHER, User.id == teacher_id))


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


def get_all_teaching_assignments_by_teacher_id(db: Session, teacher_id: int) -> list[TeachingAssignment]:
    return db.scalars(select(TeachingAssignment).where(TeachingAssignment.teacher_id == teacher_id)).all()


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


def get_exam_by_id(db: Session, exam_id: int):
    return db.scalar(select(Exam).where(Exam.id == exam_id))


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

    if exam_rule.check_exam_duration_conflict(
            db, exam_data.room_id, exam_data.exam_date, exam_data.time_frame, exam_data.duration,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phòng đã có lớp học hoặc lịch thi khác trùng khung giờ này.",
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

    # Không xếp lịch thi trùng giờ với buổi học thường (ClassSession) hoặc ca thi (Exam) khác trong cùng phòng
    if exam_rule.check_exam_duration_conflict(
            db, exam_data.room_id, exam_data.exam_date, exam_data.time_frame, exam_data.duration,
            exclude_exam_id=exam_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phòng đã có lớp học hoặc lịch thi khác trùng khung giờ này.",
        )

    for inv in exam.invigilators:
        if exam_rule.check_invigilator_conflict(
                db, inv.teacher_id, exam_data.exam_date, exam_data.time_frame, exam_data.duration,
                exclude_exam_id=exam_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Giảng viên coi thi (id={inv.teacher_id}) bị trùng lịch vào khung giờ mới.",
            )

    exam.room_id = exam_data.room_id
    exam.exam_date = exam_data.exam_date
    exam.type = exam_data.type
    exam.time_frame = exam_data.time_frame
    exam.duration = exam_data.duration
    exam.status = exam_data.status

    db.commit()
    db.refresh(exam)
    return exam


def change_exam_active(db: Session, ids: list[int]) -> list[Exam]:
    exams = db.scalars(select(Exam).where(Exam.id.in_(ids))).all()

    found_ids = {e.id for e in exams}
    missing = set(ids) - found_ids
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Không tìm thấy buổi thi với id: {sorted(missing)}")

    for exam in exams:
        new_active = not exam.is_active
        if not new_active and exam.status == ExamStatus.FINISHED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Buổi thi (id={exam.id}) đã hoàn thành (FINISHED), không thể xóa.",
            )
        exam.is_active = new_active

    db.commit()
    for exam in exams:
        db.refresh(exam)
    return exams


def get_all_exam_invigilator(db: Session, exam_id: int):
    return db.scalars(select(ExamInvigilator).where(ExamInvigilator.exam_id == exam_id)).all()


def get_all_exam_invigilator_by_id(db: Session, exam_invigilator_id: int):
    return db.scalar(select(ExamInvigilator).where(ExamInvigilator.id == exam_invigilator_id))


def get_exam_invigilator_by_teacher_id(db: Session, teacher_id: int) -> list[ExamInvigilator]:
    return db.scalars(select(ExamInvigilator).where(ExamInvigilator.teacher_id == teacher_id)).all()


def create_exam_invigilator(db: Session, exam_invigilator_data) -> ExamInvigilator:
    exam = get_exam_by_id(db, exam_invigilator_data.exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy buổi thi.")

    # giảng viên có tồn tại
    if not get_teacher_by_id(db, exam_invigilator_data.teacher_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy giảng viên."
        )

    # đã được phân công coi thi đúng ca thi này chưa
    if exam_rule.check_duplicate_exam_invigilator(db, exam.id, exam_invigilator_data.teacher_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Giảng viên đã được phân công coi thi ca thi này rồi."
        )

    # trùng lịch giảng dạy cố định (thứ/buổi) với ngày giờ của ca thi
    if exam_rule.check_teacher_teaching_conflict_with_exam(
            db, exam_invigilator_data.teacher_id, exam.exam_date, exam.time_frame, exam.duration
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Giảng viên đang có lịch giảng dạy trùng với ca thi này."
        )

    # trùng lịch coi thi khác
    if exam_rule.check_invigilator_conflict(
            db, exam_invigilator_data.teacher_id, exam.exam_date, exam.time_frame, exam.duration,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Giảng viên bị trùng lịch coi thi."
        )

    exam_invigilator = ExamInvigilator(
        teacher_id=exam_invigilator_data.teacher_id,
        exam_id=exam_invigilator_data.exam_id,
    )

    db.add(exam_invigilator)
    db.commit()
    db.refresh(exam_invigilator)

    return exam_invigilator


def update_exam_invigilator(db: Session, exam_invigilator_data, exam_invigilator_id: int) -> ExamInvigilator:
    exam_invigilator = get_all_exam_invigilator_by_id(db, exam_invigilator_id)
    if exam_invigilator is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phân công coi thi.")

    exam = exam_invigilator.exam

    # giảng viên có tồn tại
    if not get_teacher_by_id(db, exam_invigilator_data.teacher_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy giảng viên."
        )

    # đã được phân công coi thi đúng ca thi này chưa (loại trừ chính bản ghi đang sửa)
    if exam_rule.check_duplicate_exam_invigilator(
            db, exam.id, exam_invigilator_data.teacher_id, exclude_id=exam_invigilator_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Giảng viên đã được phân công coi thi ca thi này rồi."
        )

    # trùng lịch giảng dạy cố định (thứ/buổi) với ngày giờ của ca thi
    if exam_rule.check_teacher_teaching_conflict_with_exam(
            db, exam_invigilator_data.teacher_id, exam.exam_date, exam.time_frame, exam.duration
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Giảng viên đang có lịch giảng dạy trùng với ca thi này."
        )

    # trùng lịch coi thi khác (loại trừ chính bản ghi đang sửa)
    if exam_rule.check_invigilator_conflict(
            db, exam_invigilator_data.teacher_id, exam.exam_date, exam.time_frame, exam.duration,
            exclude_invigilator_id=exam_invigilator_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Giảng viên bị trùng lịch coi thi."
        )

    exam_invigilator.teacher_id = exam_invigilator_data.teacher_id

    db.commit()
    db.refresh(exam_invigilator)

    return exam_invigilator
