from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from server.models import User, UserRole, SubjectClass, TokenBlacklist, Subject, Room, Schedule, Enrollment, \
    ClassStatus, TeachingAssignment
from server.rules import teaching_rule, common_rule
from server.rules.enrollment_rule import check_subject_class_status, check_subject_class_capacity, \
    check_schedule_conflict, check_credit_limit, MAXIMUM_CREDITS
from server.rules.exam_rule import check_schedule_room_conflict
from server.rules.subject_class_rule import check_room_capacity, check_max_students_positive
from server.schemas import UserCreate, SubjectClassCreate, EnrollmentCreate, TeachingAssignmentCreate, \
    TeachingAssignmentOut, SubjectClassUpdate


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


def _generate_user_code(db: Session, role: UserRole) -> str:
    """Sinh mã user dạng SV230001 / GV230001 dựa theo role"""
    """Có thể race condition khi commit cùng lúc"""
    prefix = "SV" if role == UserRole.STUDENT else "GV" if role == UserRole.TEACHER else "AD"
    count = db.execute(
        select(func.count()).select_from(User).where(User.role == role)
    ).scalar_one()
    return f"{prefix}{count + 1:06d}"  # VD: SV000001db


def create_user(db: Session, user_data: UserCreate, max_retries: int = 3) -> User | None:
    """user_code sinh theo count() có race condition: 2 request đăng ký
    cùng lúc có thể đọc cùng count -> cùng user_code -> IntegrityError
    trên uq_users_user_code. Khác với các trường hợp trùng "thật sự" (user
    cố tình đăng ký 2 lần), đây là trùng do đếm sai lúc concurrent nên
    retry lại là hợp lý, không nên trả lỗi cho người dùng."""
    role = getattr(user_data, "role", UserRole.STUDENT)

    for attempt in range(max_retries):
        try:
            user = User(
                user_code=_generate_user_code(db, role),
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                email=user_data.email,
                role=role,
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
                continue  # thử sinh lại mã và insert lại
            raise  # email trùng hoặc hết lượt retry -> để global handler xử lý
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


def get_all_subject_class(db: Session) -> list[SubjectClass]:
    return db.scalars(select(SubjectClass)).all()


def get_subject_class_by_subject(db: Session, subject_class_id: int) -> SubjectClass | None:
    return db.scalar(select(SubjectClass).where(SubjectClass.id == subject_class_id))


def create_subject_class(db: Session, subject_class_data: SubjectClassCreate) -> tuple[SubjectClass, Schedule]:
    subject = db.get(Subject, subject_class_data.subject_id)
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Môn học không tồn tại",
        )

    room = db.get(Room, subject_class_data.room_id)
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phòng học không tồn tại",
        )

    if not check_max_students_positive(subject_class_data.max_students):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sĩ số tối đa phải lớn hơn 0",
        )

    if not check_room_capacity(subject_class_data.max_students, room.capacity):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sĩ số tối đa ({subject_class_data.max_students}) vượt quá sức chứa phòng ({room.capacity})",
        )

    if check_schedule_room_conflict(
            db,
            room_id=subject_class_data.room_id,
            weekday=subject_class_data.weekday,
            session_time=subject_class_data.session,
            semester=subject_class_data.semester,
            academic_year=subject_class_data.academic_year,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phòng đã được xếp lịch trùng thứ/buổi trong học kỳ và năm học này.",
        )

    subject_class = SubjectClass(
        subject_class_name=subject_class_data.subject_class_name,
        subject_id=subject_class_data.subject_id,
        semester=subject_class_data.semester,
        academic_year=subject_class_data.academic_year,
        status=ClassStatus.OPEN,
        max_students=subject_class_data.max_students,
    )
    db.add(subject_class)
    db.flush()

    schedule = Schedule(
        subject_class_id=subject_class.id,
        room_id=subject_class_data.room_id,
        weekday=subject_class_data.weekday,
        session=subject_class_data.session,
        semester=subject_class_data.semester,
        academic_year=subject_class_data.academic_year,
    )
    db.add(schedule)

    db.commit()
    db.refresh(subject_class)
    db.refresh(schedule)
    return subject_class, schedule


def update_subject_class(db: Session, subject_class_data: SubjectClassUpdate, subject_class_id: int) -> tuple[
    SubjectClass, Schedule]:
    subject_class = db.get(SubjectClass, subject_class_id)
    if subject_class is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lớp học phần không tồn tại")

    room = db.get(Room, subject_class_data.room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phòng học không tồn tại")

    if not check_max_students_positive(subject_class_data.max_students):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sĩ số tối đa phải lớn hơn 0")

    if not check_room_capacity(subject_class_data.max_students, room.capacity):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sĩ số tối đa ({subject_class_data.max_students}) vượt quá sức chứa phòng ({room.capacity})",
        )

    schedule = db.query(Schedule).filter(Schedule.subject_class_id == subject_class_id).first()
    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lịch học của lớp này")

    if check_schedule_room_conflict(
            db,
            room_id=subject_class_data.room_id,
            weekday=subject_class_data.weekday,
            session_time=subject_class_data.session,
            semester=subject_class_data.semester,
            academic_year=subject_class_data.academic_year,
            exclude_schedule_id=schedule.id,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phòng đã được xếp lịch trùng thứ/buổi trong học kỳ và năm học này.",
        )

    subject_class.subject_class_name = subject_class_data.subject_class_name
    subject_class.semester = subject_class_data.semester
    subject_class.academic_year = subject_class_data.academic_year
    subject_class.max_students = subject_class_data.max_students
    subject_class.status = subject_class_data.status


    schedule.room_id = subject_class_data.room_id
    schedule.weekday = subject_class_data.weekday
    schedule.session = subject_class_data.session
    schedule.semester = subject_class_data.semester
    schedule.academic_year = subject_class_data.academic_year

    db.commit()
    db.refresh(subject_class)
    db.refresh(schedule)
    return subject_class, schedule

def get_teacher(db: Session) -> list[User]:
    return db.scalars(select(User).where(User.role==UserRole.TEACHER)).all()


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

    if teaching_rule.check_duplicate_teaching_assignment(db, teaching_assignment_data.teacher_id,
                                                         teaching_assignment_data.subject_class_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Giảng viên đã được phân công giảng lớp học phần này rồi."
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

    if teaching_rule.check_duplicate_teaching_assignment(
            db, teaching_assignment_data.teacher_id, teaching_assignment_data.subject_class_id,
            exclude_assignment_id=teaching_assignment_id,
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Giảng viên đã được phân công giảng lớp học phần này rồi.")

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

    if not check_subject_class_status(subject_class):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lớp học phần không mở đăng ký (đã đóng hoặc đã kết thúc).",
        )

    if not check_subject_class_capacity(db, subject_class):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lớp học phần đã đủ sĩ số, không thể đăng ký thêm.",
        )

    if check_schedule_conflict(
            db, student_id, data.subject_class_id, data.semester, data.academic_year
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lịch học của lớp này bị trùng với một lớp bạn đã đăng ký trong học kỳ này.",
        )

    if not check_credit_limit(db, student_id, subject_class):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Đăng ký lớp này sẽ vượt quá giới hạn {MAXIMUM_CREDITS} tín chỉ trong học kỳ.",
        )

    enrollment = Enrollment(
        student_id=student_id,
        subject_class_id=data.subject_class_id,
        semester=data.semester,
        academic_year=data.academic_year,
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment
