from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from server.models import ExamRegistration, Exam, ExamInvigilator, ExamStatus, Schedule


def check_duplicate_exam_registration(
        db: Session,
        student_id,
        exam_id,
):
    return db.query(
        ExamRegistration.id
    ).filter(
        ExamRegistration.student_id == student_id,
        ExamRegistration.exam_id == exam_id,
    ).first() is not None


def check_exam_schedule_conflict(
        db: Session,
        student_id: int,
        exam_id: int,
) -> bool:
    new_exam = db.query(
        Exam.exam_date, Exam.time_frame
    ).filter(
        Exam.id == exam_id
    ).first()

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
    registered = db.query(
        ExamRegistration.id
    ).filter(
        ExamRegistration.exam_id == exam.id
    ).count()

    return registered < exam.room.capacity


def check_exam_status(exam):
    return exam.status == ExamStatus.SCHEDULED


def check_invigilator_conflict(
        db: Session,
        teacher_id: int,
        exam_id: int,
) -> bool:
    new_exam = db.query(
        Exam.exam_date, Exam.time_frame
    ).filter(
        Exam.id == exam_id
    ).first()

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
        exclude_schedule_id: int = None,
) -> bool:
    query = db.query(Schedule.id).filter(
        Schedule.room_id == room_id,
        Schedule.weekday == weekday,
        Schedule.session == session_time,
        Schedule.semester == semester,
        Schedule.academic_year == academic_year,
    )

    if exclude_schedule_id is not None:
        query = query.filter(Schedule.id != exclude_schedule_id)

    return query.first() is not None


def _exam_time_range(exam_date: datetime, time_frame, duration: int):
    start_time = datetime.strptime(time_frame.value, "%H:%M").time()
    start = datetime.combine(exam_date.date(), start_time)
    end = start + timedelta(minutes=duration)
    return start, end


def check_exam_time_overlap(
        db: Session,
        room_id: int,
        exam_date: datetime,
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