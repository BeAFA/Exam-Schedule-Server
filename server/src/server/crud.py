from sqlalchemy.orm import Session
from sqlalchemy import select
from server.models import User
from server.schemas import UserCreate

def get_user_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()

def create_user(db: Session, user_data: UserCreate) -> User:
    user = User(
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        email=user_data.email,
    )
    user.set_password(user_data.password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user