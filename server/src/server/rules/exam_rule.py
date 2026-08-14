from datetime import datetime, timedelta, date

from sqlalchemy import func
from sqlalchemy.orm import Session

from server.models import (
    ExamRegistration, Exam, ExamInvigilator, ExamStatus, Schedule, SubjectClass, ClassSession,
)


def check_duplicate_exam_registration(db: Session, student_id, exam_id):
    return db.query(ExamRegistration.id).filter(
        ExamRegistration.student_id == student_id,
        ExamRegistration.exam_id == exam_id,
    ).first() is not None


def check_exam_schedule_conflict(db: Session, student_id: int, exam_id: int) -> bool:
    new_exam = db.query(Exam.exam_date, Exam.time_frame).filter(Exam.id == exam_id).first()

    if new_exam is None:
        return False

    conflict = (
        db.query(ExamRegistration.id)
        .join(Exam, ExamRegistration.exam_id == Exam.id)
        .filter(
            ExamRegistration.student_id == student_id,
            Exam.exam_date == new_exam.exam_date,
            Exam.time_frame == new_exam.time_frame,
            Exam.id != exam_id,
        )
        .first()
    )
    return conflict is not None


def check_exam_room_capacity(db: Session, exam):
    registered = db.query(ExamRegistration.id).filter(ExamRegistration.exam_id == exam.id).count()
    return registered < exam.room.capacity


def check_exam_status(exam):
    return exam.status == ExamStatus.SCHEDULED


def check_invigilator_conflict(db: Session, teacher_id: int, exam_id: int) -> bool:
    new_exam = db.query(Exam.exam_date, Exam.time_frame).filter(Exam.id == exam_id).first()

    if new_exam is None:
        return False

    conflict = (
        db.query(ExamInvigilator.id)
        .join(Exam, ExamInvigilator.exam_id == Exam.id)
        .filter(
            ExamInvigilator.teacher_id == teacher_id,
            Exam.exam_date == new_exam.exam_date,
            Exam.time_frame == new_exam.time_frame,
            Exam.id != exam_id,
        )
        .first()
    )
    return conflict is not None


def check_schedule_room_conflict(
        db: Session,
        room_id: int,
        weekday,
        session_time,
        semester,
        academic_year: str,
        exclude_subject_class_id: int = None,
) -> bool:
    query = (
        db.query(Schedule.id)
        .join(SubjectClass, Schedule.subject_class_id == SubjectClass.id)
        .filter(
            Schedule.room_id == room_id,
            Schedule.weekday == weekday,
            Schedule.session == session_time,
            SubjectClass.semester == semester,
            SubjectClass.academic_year == academic_year,
        )
    )

    if exclude_subject_class_id is not None:
        query = query.filter(Schedule.subject_class_id != exclude_subject_class_id)

    return query.first() is not None

def get_last_class_session_date(db: Session, subject_class_id: int) -> date | None:
    """Lấy ngày của buổi học cuối cùng của lớp học phần để xếp lịch thi sau đó."""
    last_session = (
        db.query(ClassSession.session_date)
        .join(Schedule, ClassSession.schedule_id == Schedule.id)
        .filter(Schedule.subject_class_id == subject_class_id)
        .order_by(ClassSession.session_date.desc())
        .first()
    )
    return last_session[0] if last_session else None

def check_exam_date_after_last_session(db: Session, subject_class_id: int, exam_date: date) -> bool:
    """Kiểm tra ngày thi có diễn ra SAU buổi học cuối cùng không."""
    last_date = get_last_class_session_date(db, subject_class_id)
    if not last_date:
        return True # Lớp chưa có lịch trình thì bỏ qua
    return exam_date > last_date

def check_exam_conflict_with_regular_class(db: Session, subject_class_id: int, exam_date: date) -> bool:
    """Đảm bảo ngày thi (tùy chọn) không rơi trúng vào ngày mà chính sinh viên lớp đó đang có buổi học."""
    conflict = (
        db.query(ClassSession.id)
        .join(Schedule, ClassSession.schedule_id == Schedule.id)
        .filter(
            Schedule.subject_class_id == subject_class_id,
            ClassSession.session_date == exam_date
        )
        .first()
    )
    return conflict is not None

def check_room_used_by_class_session(db: Session, room_id: int, exam_date: date) -> bool:
    """Vì ClassSession.session_date và exam_date đều đã là Date, có thể so sánh trực tiếp"""
    return (
        db.query(ClassSession.id)
        .join(Schedule, ClassSession.schedule_id == Schedule.id)
        .filter(
            Schedule.room_id == room_id,
            ClassSession.session_date == exam_date,
        )
        .first()
    ) is not None


def _exam_time_range(exam_date: date, time_frame, duration: int):
    """Combine trực tiếp với đối tượng date"""
    start_time = datetime.strptime(time_frame.value, "%H:%M").time()
    start = datetime.combine(exam_date, start_time)
    end = start + timedelta(minutes=duration)
    return start, end


def check_exam_time_overlap(
        db: Session,
        room_id: int,
        exam_date: date,
        time_frame,
        duration: int,
        exclude_exam_id: int = None,
) -> bool:
    new_start, new_end = _exam_time_range(exam_date, time_frame, duration)

    query = db.query(
        Exam.id, Exam.time_frame, Exam.duration
    ).filter(
        Exam.room_id == room_id,
        Exam.exam_date == exam_date,
        Exam.status != ExamStatus.CANCELLED,
    )

    if exclude_exam_id is not None:
        query = query.filter(Exam.id != exclude_exam_id)

    for other_id, other_time_frame, other_duration in query.all():
        other_start, other_end = _exam_time_range(exam_date, other_time_frame, other_duration)
        if new_start < other_end and other_start < new_end:
            return True

    return False