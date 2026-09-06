from datetime import datetime, timezone
import uvicorn
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from server import app, get_db
from server import crud, schemas
from server.auth import create_access_token, get_current_user, require_role, \
    get_token_payload
from server.exceptions import register_exception_handlers
from server.models import UserRole

register_exception_handlers(app)

ALLOWED_TYPES = {"image/jpeg", "image/png"}
MAX_AVATAR_SIZE = 5 * 1024 * 1024


@app.get("/")
def home():
    return {"message": "Hello World"}


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


@app.get("/me", response_model=schemas.UserOut)
def read_current_user(current_user=Depends(get_current_user)):
    return current_user


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


@app.get("/schedule", response_model=list[schemas.ScheduleOut], status_code=status.HTTP_200_OK)
def get_schedule(current_user=Depends(require_role(UserRole.STUDENT, UserRole.TEACHER, UserRole.ADMIN)),
                 db: Session = Depends(get_db)):
    schedules = crud.get_all_schedule(db)
    if not schedules:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy lịch học của các lớp học phần."
        )
    return schedules


@app.get("/subject_class", response_model=list[schemas.SubjectClassOut], status_code=status.HTTP_200_OK)
def get_subject_class(current_user=Depends(require_role(UserRole.STUDENT, UserRole.TEACHER, UserRole.ADMIN)),
                      db: Session = Depends(get_db)):
    subject_classes = crud.get_all_subject_class(db)
    if not subject_classes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hiện không có lớp nào cả!")
    return subject_classes


@app.post("/subject_class/create", response_model=schemas.SubjectClassWithScheduleOut,
          status_code=status.HTTP_201_CREATED)
def create_subject_class(
        data: schemas.SubjectClassCreate,
        current_user=Depends(require_role(UserRole.ADMIN)),
        db: Session = Depends(get_db),
):
    subject_class, schedules = crud.create_subject_class(db, data)
    return schemas.SubjectClassWithScheduleOut(
        subject_class=schemas.SubjectClassOut.model_validate(subject_class),
        schedules=[schemas.ScheduleOut.model_validate(s) for s in schedules],
    )


@app.post("/subject_class/{subject_class_id}/update", response_model=schemas.SubjectClassWithScheduleOut,
          status_code=status.HTTP_200_OK)
async def update_subject_class(
        subject_class_id: int,
        data: schemas.SubjectClassUpdate,
        current_user=Depends(require_role(UserRole.ADMIN)),
        db: Session = Depends(get_db),
):
    subject_class, schedules = crud.update_subject_class(db, data, subject_class_id)
    return schemas.SubjectClassWithScheduleOut(
        subject_class=schemas.SubjectClassOut.model_validate(subject_class),
        schedules=[schemas.ScheduleOut.model_validate(s) for s in schedules],
    )


@app.post("/subject_class/change_active", response_model=list[schemas.ChangeActiveOut],
          status_code=status.HTTP_200_OK)
def change_subject_class_active(
        data: schemas.ChangeActiveIn,
        current_user=Depends(require_role(UserRole.ADMIN)),
        db: Session = Depends(get_db),
):
    subject_classes = crud.change_subject_class_active(db, data.ids, data.is_active)
    return [
        schemas.ChangeActiveOut(id=sc.id, is_active=sc.is_active)
        for sc in subject_classes
    ]


@app.get("/teacher", response_model=list[schemas.UserOut], status_code=status.HTTP_200_OK)
def get_teacher(
        current_user=Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
        db: Session = Depends(get_db)
):
    teachers = crud.get_teacher(db)
    if not teachers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hiện không có giảng viên nào cả."
        )
    return teachers


@app.get("/subject_class/{subject_class_id}/teaching_assignment",
         response_model=schemas.TeachingAssignmentOut | None,
         status_code=status.HTTP_200_OK)
def get_subject_class_teaching_assignment(
        subject_class_id: int,
        current_user=Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
        db: Session = Depends(get_db),
):
    assignment = crud.get_teaching_assignment_by_subject_class(db, subject_class_id)
    return schemas.TeachingAssignmentOut.model_validate(assignment) if assignment else None


@app.post("/teaching_assignment/create", response_model=schemas.TeachingAssignmentOut,
          status_code=status.HTTP_201_CREATED)
def create_teaching_assignment(
        data: schemas.TeachingAssignmentCreate,
        current_user=Depends(require_role(UserRole.ADMIN)),
        db: Session = Depends(get_db)
):
    teaching_assignment = crud.create_teaching_assignment(db, data)
    return schemas.TeachingAssignmentOut.model_validate(teaching_assignment)


@app.post("/teaching_assignment/{teaching_assignment_id}/update", response_model=schemas.TeachingAssignmentOut,
          status_code=status.HTTP_200_OK)
def update_teaching_assignment(
        teaching_assignment_id: int,
        data: schemas.TeachingAssignmentCreate,
        current_user=Depends(require_role(UserRole.ADMIN)),
        db: Session = Depends(get_db)
):
    teaching_assignment = crud.update_teacher_assignment(db, data, teaching_assignment_id)
    return schemas.TeachingAssignmentOut.model_validate(teaching_assignment)


@app.get("/exam", response_model=list[schemas.ExamOut], status_code=status.HTTP_200_OK)
def get_exam(
        current_user=Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
        db: Session = Depends(get_db),
):
    exams = crud.get_all_exam(db)
    if not exams:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hiện tại chưa có lịch thi của lớp học phần nào cả."
        )
    return exams


@app.post("/exam/create", response_model=schemas.ExamOut, status_code=status.HTTP_201_CREATED)
def create_exam(
        data: schemas.ExamCreate,
        current_user=Depends(require_role(UserRole.ADMIN)),
        db: Session = Depends(get_db),
):
    return crud.create_exam(db, data)


@app.post("/exam/{exam_id}/update", response_model=schemas.ExamOut, status_code=status.HTTP_200_OK)
def update_exam(
        data: schemas.ExamUpdate,
        exam_id: int,
        current_user=Depends(require_role(UserRole.ADMIN)),
        db: Session = Depends(get_db),
):
    exam = crud.update_exam(db, data, exam_id)
    return schemas.ExamOut.model_validate(exam)


@app.post("/exam/change_active", response_model=list[schemas.ChangeActiveOut], status_code=status.HTTP_200_OK)
def change_exam_active(
        data: schemas.ChangeActiveIn,
        current_user=Depends(require_role(UserRole.ADMIN)),
        db: Session = Depends(get_db),
):
    exams = crud.change_exam_active(db, data.ids, data.is_active)
    return [
        schemas.ChangeActiveOut(id=e.id, is_active=e.is_active)
        for e in exams
    ]


@app.get("/exam_invigilator", response_model=list[schemas.ExamInvigilatorOut], status_code=status.HTTP_200_OK)
def get_exam_invigilator(
        exam_id: int,
        current_user=Depends(require_role(UserRole.ADMIN)),
        db: Session = Depends(get_db),
):
    return crud.get_all_exam_invigilator(db, exam_id)


@app.post(
    "/exam_invigilator/set",
    response_model=list[schemas.ExamInvigilatorOut],
    status_code=status.HTTP_201_CREATED
)
def set_exam_invigilators(
        data: schemas.ExamInvigilatorCreate,
        current_user=Depends(require_role(UserRole.ADMIN)),
        db: Session = Depends(get_db),
):
    return crud.set_exam_invigilators(db, data)


if __name__ == "__main__":
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)
