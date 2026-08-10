from datetime import datetime, timezone

import uvicorn
from fastapi import Depends, HTTPException, status
from jose import jwt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from server import app, engine, get_db, Base
from server import crud, schemas
from server.auth import create_access_token, get_current_user, require_role, oauth2_scheme, SECRET_KEY, ALGORITHM, \
    get_token_payload
from server.models import UserRole


@app.get("/")
def home():
    return {"message": "Hello World"}


@app.post("/register", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
def register(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = crud.get_user_by_email(db, user_data.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email đã được sử dụng")
    return crud.create_user(db, user_data)


@app.post("/login")
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    user = crud.get_user_by_email(db, credentials.email)
    if not user or not user.check_password(credentials.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sai email hoặc mật khẩu")

    access_token = create_access_token(
        data={"sub": user.email, "role": user.role.value}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email,
        "role": user.role.value,
        "full_name": f"{user.first_name} {user.last_name}",
    }

@app.post("/logout")
def logout(
    payload: dict = Depends(get_token_payload),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    jti = payload.get("jti")
    exp = payload.get("exp")
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)

    crud.blacklist_token(db, jti, expires_at)
    return {"message": "Đăng xuất thành công"}


@app.get("/me")
def read_current_user(current_user=Depends(get_current_user)):
    return {
        "id": current_user.id,
        "user_code": current_user.user_code,
        "email": current_user.email,
        "full_name": f"{current_user.first_name} {current_user.last_name}",
        "role": current_user.role.value,
    }

@app.get("/subject")
def get_subject(current_user=Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)), db: Session = Depends(get_db)):
    subject = crud.get_all_subject(db)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hiện không có môn học nào cả!")
    return subject

@app.get("/room")
def get_room(current_user=Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)), db: Session = Depends(get_db)):
    rooms = crud.get_all_room(db)
    if not rooms:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hiện không có phòng nào cả!")
    return rooms

@app.get("/subject_class")
def get_subject_class(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    subject_classes = crud.get_all_subject_class(db)
    if not subject_classes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hiện không có lớp nào cả!")
    return subject_classes

@app.post("/subject_class/create", response_model=schemas.SubjectClassWithScheduleOut, status_code=status.HTTP_201_CREATED)
def create_subject_class(
    data: schemas.SubjectClassCreate,
    current_user=Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    try:
        subject_class, schedule = crud.create_subject_class(db, data)
        return schemas.SubjectClassWithScheduleOut(
            subject_class=schemas.SubjectClassOut.model_validate(subject_class),
            schedule=schemas.ScheduleOut.model_validate(schedule),
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phòng đã được xếp lịch trùng thứ/buổi trong học kỳ + năm học này, "
                   "hoặc lớp học phần đã tồn tại (trùng môn/tên lớp/kỳ/năm).",
        )

if __name__ == "__main__":
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)
