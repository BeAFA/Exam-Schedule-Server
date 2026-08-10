from pydantic import BaseModel, EmailStr, ConfigDict

from server.models import Semester, ClassStatus


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
    first_name: str
    last_name: str
    email: EmailStr

class SubjectClassCreate(BaseModel):
    subject_class_name: str
    subject_id:int
    semester: Semester
    academic_year: str
    status: ClassStatus
    max_students: int

class SubjectClassOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    subject_class_name: str
    subject_id: int
    semester: Semester
    academic_year: str
    status: ClassStatus
    max_students: int | None