from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import select, func
from server.models import User, UserRole, SubjectClass, TokenBlacklist, Subject, Room, Schedule
from server.schemas import UserCreate, SubjectClassCreate


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


def _generate_user_code(db: Session, role: UserRole) -> str:
    """Sinh mã user dạng SV230001 / GV230001 dựa theo role"""
    prefix = "SV" if role == UserRole.STUDENT else "GV" if role == UserRole.TEACHER else "AD"
    count = db.execute(
        select(func.count()).select_from(User).where(User.role == role)
    ).scalar_one()
    return f"{prefix}{count + 1:06d}"  # VD: SV000001


def create_user(db: Session, user_data: UserCreate) -> User:
    role = getattr(user_data, "role", UserRole.STUDENT)

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
    """Tạo SubjectClass VÀ Schedule (phòng + thứ + buổi) đi kèm trong CÙNG 1
    transaction. Dùng flush() để lấy subject_class.id trước khi có Schedule
    tham chiếu tới, nhưng chỉ commit MỘT LẦN ở cuối — nếu Schedule vi phạm
    UniqueConstraint (room_id, weekday, session, semester, academic_year,
    tức phòng đã bị xếp lịch trùng giờ), commit sẽ raise IntegrityError và
    CẢ HAI record đều bị rollback, tránh tạo ra lớp học phần "mồ côi" không
    có lịch học hợp lệ.
    """
    subject_class = SubjectClass(
        subject_class_name=subject_class_data.subject_class_name,
        subject_id=subject_class_data.subject_id,
        semester=subject_class_data.semester,
        academic_year=subject_class_data.academic_year,
        status=subject_class_data.status,
        max_students=subject_class_data.max_students,
    )
    db.add(subject_class)
    db.flush()  # sinh subject_class.id mà chưa commit

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