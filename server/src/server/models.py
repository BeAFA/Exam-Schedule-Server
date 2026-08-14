from enum import Enum
from datetime import datetime, date, timedelta, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import (
    Integer, String, DateTime, Float,
    Enum as SQLEnum, ForeignKey, UniqueConstraint, Date, select
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session

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
    NOT_MARKED = "NOT_MARKED"
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    EXCUSED = "EXCUSED"


class ClassStatus(Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    FINISHED = "FINISHED"


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

WEEKDAY_TO_PYTHON = {
    Weekday.MON: 0,
    Weekday.TUE: 1,
    Weekday.WED: 2,
    Weekday.THU: 3,
    Weekday.FRI: 4,
    Weekday.SAT: 5,
    Weekday.SUN: 6,
}


class SessionEN(Enum):
    MORNING = "MORNING"
    AFTERNOON = "AFTERNOON"

SESSION_ORDER = {
    SessionEN.MORNING: 1,
    SessionEN.AFTERNOON: 2,
}


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
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    number_of_sessions: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ClassStatus] = mapped_column(SQLEnum(ClassStatus), nullable=False, default=ClassStatus.OPEN)
    max_students: Mapped[int] = mapped_column(Integer, nullable=False)

    subject: Mapped["Subject"] = relationship(back_populates="classes")
    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="subject_class")
    teaching_assignments: Mapped[list["TeachingAssignment"]] = relationship(back_populates="subject_class")
    exams: Mapped[list["Exam"]] = relationship(back_populates="subject_class")
    schedules: Mapped[list["Schedule"]] = relationship(back_populates="subject_class", cascade="all, delete-orphan")
    class_sessions: Mapped[list["ClassSession"]] = relationship(back_populates="subject_class", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("subject_id", "subject_class_name", "semester", "academic_year", name="uq_class_identity"),
    )


# ================= ROOM =================
class Room(Base, Classify):
    __tablename__ = "rooms"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)

    exams: Mapped[list["Exam"]] = relationship(back_populates="room")
    schedules: Mapped[list["Schedule"]] = relationship(back_populates="room")
    class_sessions: Mapped[list["ClassSession"]] = relationship(back_populates="room")


# ================= SCHEDULE =================
class Schedule(Base, Classify):
    __tablename__ = "schedules"

    subject_class_id: Mapped[int] = mapped_column(ForeignKey(SubjectClass.id), nullable=False)
    room_id: Mapped[int] = mapped_column(ForeignKey(Room.id), nullable=False)
    weekday: Mapped[Weekday] = mapped_column(SQLEnum(Weekday), nullable=False)
    session: Mapped[SessionEN] = mapped_column(SQLEnum(SessionEN), nullable=False, comment="Buổi sáng/chiều")

    subject_class: Mapped["SubjectClass"] = relationship(back_populates="schedules")
    room: Mapped["Room"] = relationship(back_populates="schedules")
    class_sessions: Mapped[list["ClassSession"]] = relationship(back_populates="schedule", cascade="all, delete-orphan",)

    __table_args__ = (
        UniqueConstraint("subject_class_id", "weekday", "session", name="uq_subject_class_weekday_session"),
    )

# ============================================================
# CREATE SCHEDULES + GENERATE CLASS SESSIONS
# ============================================================

def create_schedules_and_sessions(
    db: Session,
    subject_class: SubjectClass,
    schedule_data: list[dict],
) -> list[Schedule]:

    if not schedule_data:
        raise ValueError("Phải có ít nhất một Schedule.")

    seen: set[tuple[Weekday, SessionEN]] = set()

    for data in schedule_data:
        weekday = data["weekday"]
        session = data["session"]

        key = (weekday, session)

        if key in seen:
            raise ValueError(
                f"Schedule bị trùng "
                f"{weekday.value} - {session.value}."
            )

        seen.add(key)

    schedules: list[Schedule] = []

    for data in schedule_data:
        schedule = Schedule(
            subject_class_id=subject_class.id,
            room_id=data["room_id"],
            weekday=data["weekday"],
            session=data["session"],
        )

        db.add(schedule)
        schedules.append(schedule)

    db.flush()

    # Lấy TOÀN BỘ schedule của SubjectClass
    all_schedules = db.scalars(
        select(Schedule)
        .where(Schedule.subject_class_id == subject_class.id)
    ).all()

    generate_class_sessions(
        db=db,
        subject_class=subject_class,
        schedules=all_schedules,
    )

    return schedules

# ================= Class Session =================
class ClassSession(Base, Classify):
    __tablename__ = "class_sessions"

    subject_class_id: Mapped[int] = mapped_column(ForeignKey(SubjectClass.id), nullable=False)
    schedule_id: Mapped[int] = mapped_column(ForeignKey(Schedule.id), nullable=False)
    session_number: Mapped[int] = mapped_column(Integer, nullable=False)
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    room_id: Mapped[int] = mapped_column(ForeignKey(Room.id), nullable=False)
    weekday: Mapped[Weekday] = mapped_column(SQLEnum(Weekday), nullable=False)
    session: Mapped[SessionEN] = mapped_column(SQLEnum(SessionEN), nullable=False, comment="Buổi sáng/chiều")

    room: Mapped["Room"] = relationship(back_populates="class_sessions")
    subject_class: Mapped["SubjectClass"] = relationship(back_populates="class_sessions")
    schedule: Mapped["Schedule"] = relationship(back_populates="class_sessions")

    __table_args__ = (
        UniqueConstraint("subject_class_id", "session_number", name="uq_class_session_number"),
    )

# ============================================================
# CLASS SESSION GENERATION
# ============================================================

def generate_class_sessions(
    db: Session,
    subject_class: SubjectClass,
    schedules: list[Schedule] | None = None,
) -> list[ClassSession]:

    # ========================================================
    # VALIDATE
    # ========================================================

    if subject_class.number_of_sessions <= 0:
        raise ValueError(
            "number_of_sessions phải lớn hơn 0."
        )

    if subject_class.start_date is None:
        raise ValueError(
            "SubjectClass phải có start_date."
        )

    schedules = (
        schedules
        if schedules is not None
        else subject_class.schedules
    )

    if not schedules:
        raise ValueError(
            "SubjectClass chưa có Schedule."
        )

    # ========================================================
    # KIỂM TRA SCHEDULE
    # ========================================================

    valid_schedules: list[Schedule] = []

    seen: set[tuple[Weekday, SessionEN]] = set()

    for schedule in schedules:
        if schedule.subject_class_id != subject_class.id:
            raise ValueError(
                "Schedule không thuộc SubjectClass này."
            )

        key = (
            schedule.weekday,
            schedule.session,
        )

        if key in seen:
            raise ValueError(
                f"Schedule bị trùng "
                f"{schedule.weekday.value} - "
                f"{schedule.session.value}."
            )

        seen.add(key)
        valid_schedules.append(schedule)
    valid_schedules.sort(
        key=lambda sch: (
            WEEKDAY_TO_PYTHON[sch.weekday],
            SESSION_ORDER[sch.session],
        )
    )

    # ========================================================
    # XÓA CLASS SESSION CŨ
    # ========================================================

    for class_session in list(subject_class.class_sessions):
        db.delete(class_session)

    db.flush()

    # ========================================================
    # SINH CLASS SESSION
    # ========================================================

    sessions: list[ClassSession] = []

    current_date = subject_class.start_date
    session_number = 1

    max_days = max(
        subject_class.number_of_sessions * 14,
        30,
    )

    days_checked = 0

    while (
        session_number <= subject_class.number_of_sessions
        and days_checked <= max_days
    ):

        # ----------------------------------------------------
        # Tìm Schedule phù hợp với ngày hiện tại
        # ----------------------------------------------------

        for schedule in valid_schedules:

            target_weekday = WEEKDAY_TO_PYTHON[
                schedule.weekday
            ]

            if current_date.weekday() != target_weekday:
                continue

            # ------------------------------------------------
            # Tạo ClassSession
            # ------------------------------------------------

            class_session = ClassSession(
                subject_class_id=subject_class.id,

                schedule_id=schedule.id,

                session_number=session_number,

                session_date=current_date,

                # Snapshot Schedule
                room_id=schedule.room_id,
                weekday=schedule.weekday,
                session=schedule.session,
            )

            db.add(class_session)
            sessions.append(class_session)

            session_number += 1

            if session_number > subject_class.number_of_sessions:
                break

        current_date += timedelta(days=1)
        days_checked += 1

    # ========================================================
    # KHÔNG SINH ĐỦ SESSION
    # ========================================================

    if session_number <= subject_class.number_of_sessions:
        raise ValueError(
            "Không thể sinh đủ ClassSession. "
            "Kiểm tra start_date và Schedule của SubjectClass."
        )

    db.flush()

    return sessions


# ================= EXAM =================
class Exam(Base, Classify):
    __tablename__ = "exams"

    subject_class_id: Mapped[int] = mapped_column(ForeignKey(SubjectClass.id), nullable=False)
    room_id: Mapped[int] = mapped_column(ForeignKey(Room.id), nullable=False)
    exam_date: Mapped[date] = mapped_column(Date, nullable=False)
    type: Mapped[TypeOfExam] = mapped_column(SQLEnum(TypeOfExam), nullable=False, default=TypeOfExam.MIDTERM)
    time_frame: Mapped[TimeFrame] = mapped_column(SQLEnum(TimeFrame), nullable=False, default=TimeFrame.SHIFT_1)
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
    seat_number: Mapped[str] = mapped_column(String(10), nullable=False, comment="VD: A01, A02")
    attendance_status: Mapped[AttendanceStatus] = mapped_column(
        SQLEnum(AttendanceStatus), nullable=False, default=AttendanceStatus.NOT_MARKED
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
    registered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    final_score: Mapped[float] = mapped_column(Float, nullable=True,
                                               comment="Điểm tổng kết môn (sau khi có điểm giữa kỳ + cuối kỳ)")

    student: Mapped["User"] = relationship(back_populates="enrollments")
    subject_class: Mapped["SubjectClass"] = relationship(back_populates="enrollments")

    __table_args__ = (
        UniqueConstraint("student_id", "subject_class_id", name="uq_student_subject_class"),
    )


# ================= TEACHING - ASSIGNMENT =================
class TeachingAssignment(Base, Classify):
    __tablename__ = "teaching_assignments"

    teacher_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    subject_class_id: Mapped[int] = mapped_column(ForeignKey(SubjectClass.id), nullable=False)

    teacher: Mapped["User"] = relationship(back_populates="teaching_assignments")
    subject_class: Mapped["SubjectClass"] = relationship(back_populates="teaching_assignments")

    __table_args__ = (
        UniqueConstraint("subject_class_id", name="uq_subject_class_teacher"),
    )

# ================= TOKEN BLACKLIST =================
class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"

    jti: Mapped[str] = mapped_column(String(255), primary_key=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)