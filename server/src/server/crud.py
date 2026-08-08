from sqlalchemy.orm import Session
from sqlalchemy import select, func
from server.models import User, UserRole
from server.schemas import UserCreate

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
    )

    user.set_password(user_data.password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user