import re
from datetime import date
from pydantic import BaseModel, EmailStr, ConfigDict, field_validator, conlist
from server.models import (
    Semester, ClassStatus, Weekday, SessionEN,
    TypeOfExam, TimeFrame, ExamStatus, UserRole
)


# ================= USER =================
class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_code: str
    first_name: str
    last_name: str
    avatar: str
    email: EmailStr
    role: UserRole


# ================= SUBJECT =================
class SubjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    subject_code: str
    name: str
    credits: int


# ================= ROOM =================
class RoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    capacity: int


# ================= SCHEDULE =================
class ScheduleItem(BaseModel):
    weekday: Weekday
    session: SessionEN
    room_id: int


class ScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    subject_class_id: int
    room_id: int
    room: RoomOut
    weekday: Weekday
    session: SessionEN


# ================= SUBJECT CLASS =================
class SubjectClassBase(BaseModel):
    subject_class_name: str
    semester: Semester
    academic_year: str
    max_students: int
    start_date: date
    number_of_sessions: int
    schedules: list[ScheduleItem]

    @field_validator("academic_year")
    @classmethod
    def validate_academic_year(cls, v: str) -> str:
        if not re.fullmatch(r"\d{4}-\d{4}", v):
            raise ValueError("academic_year phải có định dạng YYYY-YYYY, VD: 2025-2026")
        y1, y2 = int(v[:4]), int(v[5:])
        if y2 != y1 + 1:
            raise ValueError("Năm sau phải liền kề năm trước, VD: 2025-2026")
        return v

    @field_validator("schedules")
    @classmethod
    def validate_schedules(cls, v: list["ScheduleItem"]) -> list["ScheduleItem"]:
        if not v:
            raise ValueError("Phải có ít nhất một lịch học (thứ/buổi/phòng).")
        seen = set()
        for item in v:
            key = (item.weekday, item.session)
            if key in seen:
                raise ValueError(f"Lịch học bị trùng: {item.weekday.value} - {item.session.value}")
            seen.add(key)
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
    subject: SubjectOut
    semester: Semester
    academic_year: str
    start_date: date
    number_of_sessions: int
    status: ClassStatus
    max_students: int
    is_active: bool


class SubjectClassWithScheduleOut(BaseModel):
    subject_class: SubjectClassOut
    schedules: list[ScheduleOut]


# ================= TEACHING ASSIGNMENT =================
class TeachingAssignmentCreate(BaseModel):
    teacher_id: int
    subject_class_id: int


class TeachingAssignmentOut(TeachingAssignmentCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool


# ================= EXAM =================
class ExamBase(BaseModel):
    room_id: int
    exam_date: date
    type: TypeOfExam
    time_frame: TimeFrame
    duration: int


class ExamCreate(ExamBase):
    subject_class_id: int


class ExamUpdate(ExamBase):
    status: ExamStatus


class ExamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    subject_class_id: int
    room_id: int
    exam_date: date
    type: TypeOfExam
    time_frame: TimeFrame
    duration: int
    status: ExamStatus
    is_active: bool


# ================= EXAM INVIGILATOR =================
class ExamInvigilatorCreate(BaseModel):
    exam_id: int
    teacher_ids: conlist(int, min_length=1)


class ExamInvigilatorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    exam_id: int
    teacher_id: int
    is_active: bool


# ================= CHANGE ACTIVE STATUS =================
class ChangeActiveIn(BaseModel):
    ids: conlist(int, min_length=1)
    is_active: bool


class ChangeActiveOut(BaseModel):
    id: int
    is_active: bool
