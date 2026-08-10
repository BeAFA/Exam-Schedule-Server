from pydantic import BaseModel, EmailStr, ConfigDict

from server.models import Semester, ClassStatus, Weekday, Session


class UserCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_code: str
    first_name: str
    last_name: str
    email: EmailStr

class SubjectCreate(BaseModel):
    subject_code: str
    name: str
    credits: int

class SubjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    subject_code: str
    name: str
    credits: int


class RoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    capacity: int


class SubjectClassCreate(BaseModel):
    subject_class_name: str
    subject_id: int
    semester: Semester
    academic_year: str
    status: ClassStatus
    max_students: int
    # Thông tin lịch học đi kèm khi tạo lớp — tạo cùng lúc với SubjectClass
    # trong 1 transaction (xem crud.create_subject_class).
    room_id: int
    weekday: Weekday
    session: Session


class SubjectClassOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    subject_class_name: str
    subject_id: int
    semester: Semester
    academic_year: str
    status: ClassStatus
    max_students: int | None


class ScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    subject_class_id: int
    room_id: int
    weekday: Weekday
    session: Session
    semester: Semester
    academic_year: str


class SubjectClassWithScheduleOut(BaseModel):
    """Trả về đầy đủ lớp học phần + lịch học vừa tạo, dùng cho response
    của endpoint tạo mới (SubjectClassOut không nhìn thấy Schedule vì
    SubjectClass model chỉ có `schedules` dạng list, không có 1-1)."""
    subject_class: SubjectClassOut
    schedule: ScheduleOut