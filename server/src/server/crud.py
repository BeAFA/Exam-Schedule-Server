from sqlalchemy.orm import Session
from sqlalchemy import select, func
from server.models import User, UserRole, SubjectClass
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


def get_all_subject_class(db: Session) -> list[SubjectClass]:
    return db.scalars(select(SubjectClass)).all()


def get_subject_classes_by_id(
        db: Session,
        subject_class_id: int
) -> SubjectClass:
    return db.scalar(select(SubjectClass).where(SubjectClass.id == subject_class_id))


def get_subject_class_by_subject(db: Session, subject_class_id: int) -> SubjectClass | None:
    return db.scalar(select(SubjectClass).where(SubjectClass.id == subject_class_id))

def create_subject_class(db: Session, subject_class_data: SubjectClassCreate) -> SubjectClass:
    subject_class = SubjectClass(
        subject_class_name = subject_class_data.subject_class_name,
        subject_id = subject_class_data.subject_id,
        semester = subject_class_data.semester,
        academic_year = subject_class_data.academic_year,
        status = subject_class_data.status,
        max_students = subject_class_data.max_students,
    )
    db.add(subject_class)
    db.commit()
    db.refresh(subject_class)
    return subject_class