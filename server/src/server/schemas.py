import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, ConfigDict, field_validator

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


class SubjectClassBase(BaseModel):
    subject_class_name: str
    semester: Semester
    academic_year: str
    max_students: int
    room_id: int
    weekday: Weekday
    session: Session

    @field_validator("academic_year")
    @classmethod
    def validate_academic_year(cls, v: str) -> str:
        if not re.fullmatch(r"\d{4}-\d{4}", v):
            raise ValueError("academic_year phải có định dạng YYYY-YYYY, VD: 2025-2026")
        y1, y2 = int(v[:4]), int(v[5:])
        if y2 != y1 + 1:
            raise ValueError("Năm sau phải liền kề năm trước, VD: 2025-2026")
        return v


class SubjectClassCreate(SubjectClassBase):
    subject_id: int


class SubjectClassUpdate(SubjectClassBase):
    status: ClassStatus


class SubjectClassOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    subject_class_name: str
    subject_id: int
    semester: Semester
    academic_year: str
    status: ClassStatus
    max_students: int


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
    subject_class: SubjectClassOut
    schedule: ScheduleOut


class TeachingAssignmentCreate(BaseModel):
    teacher_id: int
    subject_class_id: int


class TeachingAssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    teacher_id: int
    subject_class_id: int


class EnrollmentCreate(BaseModel):
    subject_class_id: int
    semester: Semester
    academic_year: str


class EnrollmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    student_id: int
    subject_class_id: int
    semester: Semester
    academic_year: str
    registered_at: datetime
