import uvicorn
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from server import app, engine, get_db, Base
from server import crud, schemas
from server.auth import create_access_token, get_current_user


@app.get("/")
@app.get("/home")
def home():
    return {"message": "Hello World"}


@app.post("/register", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
def register(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = crud.get_user_by_email(db, user_data.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email đã được sử dụng")
    return crud.create_user(db, user_data)


@app.post("/login")
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    user = crud.get_user_by_email(db, credentials.email)
    if not user or not user.check_password(credentials.password):
        raise HTTPException(status_code=401, detail="Sai email hoặc mật khẩu")

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


@app.get("/me")
def read_current_user(current_user=Depends(get_current_user)):
    return {
        "id": current_user.id,
        "user_code": current_user.user_code,
        "email": current_user.email,
        "full_name": f"{current_user.first_name} {current_user.last_name}",
        "role": current_user.role.value,
    }


if __name__ == "__main__":
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)
