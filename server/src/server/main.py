import uvicorn
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from server import app, engine, get_db, Base
from server import crud, schemas


Base.metadata.create_all(bind=engine)

@app.get("/")
def read_root():
    return {"Hello World"}

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
    return {"msg": "Đăng nhập thành công", "user_id": user.id}


if __name__ == "__main__":
    uvicorn.run(app)
