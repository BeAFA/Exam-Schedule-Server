from enum import Enum
from datetime import datetime

from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import (
    Integer, String, DateTime, Float,
    Enum as SQLEnum, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server import Base, Classify

# ================= ENUMS =================
class UserRole(Enum):
    ADMIN = "ADMIN"
    TEACHER = "TEACHER"
    STUDENT = "STUDENT"


class TypeOfExam(Enum):
    MIDTERM = "MIDTERM"
    FINALTEST = "FINALTEST"


class TimeFrame(Enum):
    SHIFT_1 = "07:30"
    SHIFT_2 = "09:50"
    SHIFT_3 = "13:00"
    SHIFT_4 = "15:20"
    SHIFT_5 = "18:00"


class Semester(Enum):
    Semester_1 = "Semester 1"
    Semester_2 = "Semester 2"
    Semester_3 = "Semester 3"


class AttendanceStatus(Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    EXCUSED = "EXCUSED"


class ClassStatus(Enum):
    OPEN = "OPEN"  # đang mở đăng ký
    CLOSED = "CLOSED"  # đã đóng đăng ký, đang học
    FINISHED = "FINISHED"  # đã kết thúc lớp


class ExamStatus(Enum):
    SCHEDULED = "SCHEDULED"
    FINISHED = "FINISHED"
    CANCELLED = "CANCELLED"


class Weekday(Enum):
    MON = "MON"
    TUE = "TUE"
    WED = "WED"
    THU = "THU"
    FRI = "FRI"
    SAT = "SAT"
    SUN = "SUN"


class Session(Enum):
    MORNING = "MORNING"  # buổi sáng
    AFTERNOON = "AFTERNOON"  # buổi chiều


# ================= USER =================
class User(Base, Classify):
    __tablename__ = "users"

    user_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, comment="VD: GV001, SV230001")
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), nullable=False, default=UserRole.STUDENT)

    # relationships
    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="student")
    teaching_assignments: Mapped[list["TeachingAssignment"]] = relationship(back_populates="teacher")
    invigilations: Mapped[list["ExamInvigilator"]] = relationship(back_populates="teacher")
    exam_registrations: Mapped[list["ExamRegistration"]] = relationship(back_populates="student")

    def set_password(self, password: str):
        self.password = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password, password)


# ================= SUBJECT =================
class Subject(Base, Classify):
    __tablename__ = "subjects"

    subject_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, comment="VD: IT001, CTDLGT")
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)

    classes: Mapped[list["SubjectClass"]] = relationship(back_populates="subject")


# ================= SUBJECT - CLASS =================
class SubjectClass(Base, Classify):
    __tablename__ = "class_rooms"

    subject_class_name: Mapped[str] = mapped_column(String(100), nullable=False)
    subject_id: Mapped[int] = mapped_column(ForeignKey(Subject.id), nullable=False)
    semester: Mapped[Semester] = mapped_column(SQLEnum(Semester), nullable=False, default=Semester.Semester_1)
    academic_year: Mapped[str] = mapped_column(String(9), nullable=False, comment="VD: 2025-2026")
    status: Mapped[ClassStatus] = mapped_column(SQLEnum(ClassStatus), nullable=False, default=ClassStatus.OPEN)
    max_students: Mapped[int] = mapped_column(Integer, nullable=True)

    subject: Mapped["Subject"] = relationship(back_populates="classes")
    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="subject_class")
    teaching_assignments: Mapped[list["TeachingAssignment"]] = relationship(back_populates="subject_class")
    exams: Mapped[list["Exam"]] = relationship(back_populates="subject_class")
    schedules: Mapped[list["Schedule"]] = relationship(back_populates="subject_class")

    __table_args__ = (
        # Không cho trùng tên lớp trong cùng 1 môn + kỳ + năm học
        UniqueConstraint("subject_id", "subject_class_name", "semester", "academic_year", name="uq_class_identity"),
    )


# ================= ROOM =================
class Room(Base, Classify):
    __tablename__ = "rooms"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    # Trạng thái trống/bận tính động dựa trên Exam / Schedule, không lưu tĩnh

    exams: Mapped[list["Exam"]] = relationship(back_populates="room")
    schedules: Mapped[list["Schedule"]] = relationship(back_populates="room")


# ================= SCHEDULE (lịch học hàng tuần) =================
class Schedule(Base, Classify):
    __tablename__ = "schedules"

    subject_class_id: Mapped[int] = mapped_column(ForeignKey(SubjectClass.id), nullable=False)
    room_id: Mapped[int] = mapped_column(ForeignKey(Room.id), nullable=False)
    weekday: Mapped[Weekday] = mapped_column(SQLEnum(Weekday), nullable=False)
    session: Mapped[Session] = mapped_column(SQLEnum(Session), nullable=False, comment="Buổi sáng/chiều")

    subject_class: Mapped["SubjectClass"] = relationship(back_populates="schedules")
    room: Mapped["Room"] = relationship(back_populates="schedules")

    __table_args__ = (
        # Chặn 1 phòng bị xếp 2 lớp cùng thứ + cùng buổi
        UniqueConstraint("room_id", "weekday", "session", name="uq_room_weekday_session"),
    )


# ================= EXAM =================
class Exam(Base, Classify):
    __tablename__ = "exam"

    subject_class_id: Mapped[int] = mapped_column(ForeignKey(SubjectClass.id), nullable=False)
    room_id: Mapped[int] = mapped_column(ForeignKey(Room.id), nullable=False)
    exam_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    type: Mapped[TypeOfExam] = mapped_column(SQLEnum(TypeOfExam), nullable=False, default=TypeOfExam.MIDTERM)
    time_frame: Mapped[TimeFrame] = mapped_column(SQLEnum(TimeFrame), nullable=False, default=TimeFrame.SHIFT_1)
    semester: Mapped[Semester] = mapped_column(SQLEnum(Semester), nullable=False, default=Semester.Semester_1)
    duration: Mapped[int] = mapped_column(Integer, nullable=False, comment="Time limit in minutes")
    status: Mapped[ExamStatus] = mapped_column(SQLEnum(ExamStatus), nullable=False, default=ExamStatus.SCHEDULED)

    subject_class: Mapped["SubjectClass"] = relationship(back_populates="exams")
    room: Mapped["Room"] = relationship(back_populates="exams")
    invigilators: Mapped[list["ExamInvigilator"]] = relationship(back_populates="exam")
    registrations: Mapped[list["ExamRegistration"]] = relationship(back_populates="exam")

    __table_args__ = (
        # Không cho xếp trùng phòng + trùng giờ + trùng ngày thi
        UniqueConstraint("room_id", "exam_date", "time_frame", name="uq_room_datetime"),
    )


# ================= EXAM - INVIGILATOR =================
class ExamInvigilator(Base, Classify):
    __tablename__ = "exam_invigilators"

    exam_id: Mapped[int] = mapped_column(ForeignKey(Exam.id), nullable=False)
    teacher_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)

    exam: Mapped["Exam"] = relationship(back_populates="invigilators")
    teacher: Mapped["User"] = relationship(back_populates="invigilations")

    __table_args__ = (
        UniqueConstraint("exam_id", "teacher_id", name="uq_exam_teacher"),
    )


# ================= EXAM - REGISTRATION (sinh viên <-> ca thi cụ thể) =================
class ExamRegistration(Base, Classify):
    __tablename__ = "exam_registrations"

    exam_id: Mapped[int] = mapped_column(ForeignKey(Exam.id), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    seat_number: Mapped[str] = mapped_column(String(10), nullable=True, comment="VD: A01, A02")
    attendance_status: Mapped[AttendanceStatus] = mapped_column(
        SQLEnum(AttendanceStatus), nullable=False, default=AttendanceStatus.PRESENT
    )
    score: Mapped[float] = mapped_column(Float, nullable=True)

    exam: Mapped["Exam"] = relationship(back_populates="registrations")
    student: Mapped["User"] = relationship(back_populates="exam_registrations")

    __table_args__ = (
        UniqueConstraint("exam_id", "student_id", name="uq_exam_student"),
        UniqueConstraint("exam_id", "seat_number", name="uq_exam_seat"),
    )


# ================= ENROLLMENT (đăng ký học phần) =================
class Enrollment(Base, Classify):
    __tablename__ = "enrollments"

    student_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    subject_class_id: Mapped[int] = mapped_column(ForeignKey(SubjectClass.id), nullable=False)
    semester: Mapped[Semester] = mapped_column(SQLEnum(Semester), nullable=False, default=Semester.Semester_1)
    registered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    final_score: Mapped[float] = mapped_column(Float, nullable=True,
                                               comment="Điểm tổng kết môn (sau khi có điểm giữa kỳ + cuối kỳ)")

    student: Mapped["User"] = relationship(back_populates="enrollments")
    subject_class: Mapped["SubjectClass"] = relationship(back_populates="enrollments")

    __table_args__ = (
        UniqueConstraint("student_id", "subject_class_id", "semester", name="uq_student_class_semester"),
    )


# ================= TEACHING - ASSIGNMENT =================
class TeachingAssignment(Base, Classify):
    __tablename__ = "teaching_assignments"

    teacher_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    subject_class_id: Mapped[int] = mapped_column(ForeignKey(SubjectClass.id), nullable=False)

    teacher: Mapped["User"] = relationship(back_populates="teaching_assignments")
    subject_class: Mapped["SubjectClass"] = relationship(back_populates="teaching_assignments")

    __table_args__ = (
        UniqueConstraint("teacher_id", "subject_class_id", name="uq_teacher_class"),
    )
