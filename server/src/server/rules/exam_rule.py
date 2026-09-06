from datetime import datetime, timedelta, date, time
from sqlalchemy.orm import Session
from server.models import (
    Exam, ExamInvigilator, ExamStatus, Schedule, SubjectClass, ClassSession, SessionEN,
    TeachingAssignment, WEEKDAY_TO_PYTHON,
)

SESSION_TIME_RANGE = {
    SessionEN.MORNING: (time(7, 0), time(11, 30)),
    SessionEN.AFTERNOON: (time(13, 0), time(17, 30)),
}


def check_exam_status(exam):
    return exam.status == ExamStatus.SCHEDULED or exam.status == ExamStatus.CANCELLED


def check_invigilator_conflict(
        db: Session,
        teacher_id: int,
        exam_date: date,
        time_frame,
        duration: int,
        exclude_exam_id: int = None,
        exclude_invigilator_id: int = None,
) -> bool:
    new_start, new_end = _exam_time_range(exam_date, time_frame, duration)

    query = (
        db.query(Exam.id, Exam.time_frame, Exam.duration)
        .join(ExamInvigilator, ExamInvigilator.exam_id == Exam.id)
        .filter(
            ExamInvigilator.teacher_id == teacher_id,
            ExamInvigilator.is_active.is_(True),
            Exam.exam_date == exam_date,
            Exam.status != ExamStatus.CANCELLED,
            Exam.is_active.is_(True),
        )
    )
    if exclude_exam_id is not None:
        query = query.filter(Exam.id != exclude_exam_id)
    if exclude_invigilator_id is not None:
        query = query.filter(
            ExamInvigilator.id != exclude_invigilator_id
        )

    for _, other_time_frame, other_duration in query.all():

        other_start, other_end = _exam_time_range(
            exam_date,
            other_time_frame,
            other_duration
        )

        if new_start < other_end and other_start < new_end:
            return True

    return False


def check_duplicate_exam_invigilator(
        db: Session,
        exam_id: int,
        teacher_id: int,
        exclude_id: int = None,
) -> bool:
    query = db.query(ExamInvigilator.id).filter(
        ExamInvigilator.exam_id == exam_id,
        ExamInvigilator.teacher_id == teacher_id,
        ExamInvigilator.is_active == True,
    )
    if exclude_id is not None:
        query = query.filter(ExamInvigilator.id != exclude_id)
    return query.first() is not None


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
            SubjectClass.is_active == True,
        )
    )

    if exclude_subject_class_id is not None:
        query = query.filter(Schedule.subject_class_id != exclude_subject_class_id)

    return query.first() is not None


def get_last_class_session_date(db: Session, subject_class_id: int) -> date | None:
    last_session = (
        db.query(ClassSession.session_date)
        .filter(ClassSession.subject_class_id == subject_class_id)
        .order_by(ClassSession.session_date.desc())
        .first()
    )
    return last_session[0] if last_session else None


def check_exam_date_after_last_session(db: Session, subject_class_id: int, exam_date: date) -> bool:
    last_date = get_last_class_session_date(db, subject_class_id)
    if not last_date:
        return True
    return exam_date > last_date


def _exam_time_range(exam_date: date, time_frame, duration: int):
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
        Exam.is_active == True,
    )

    if exclude_exam_id is not None:
        query = query.filter(Exam.id != exclude_exam_id)

    for other_id, other_time_frame, other_duration in query.all():
        other_start, other_end = _exam_time_range(exam_date, other_time_frame, other_duration)
        if new_start < other_end and other_start < new_end:
            return True

    return False


def _session_time_range(session_date: date, session: SessionEN):
    start_t, end_t = SESSION_TIME_RANGE[session]
    return datetime.combine(session_date, start_t), datetime.combine(session_date, end_t)


def check_exam_duration_conflict(
        db: Session,
        room_id: int,
        exam_date: date,
        time_frame,
        duration: int,
        exclude_exam_id: int = None,
) -> bool:
    new_start, new_end = _exam_time_range(exam_date, time_frame, duration)

    class_sessions = (
        db.query(ClassSession.session)
        .join(SubjectClass, ClassSession.subject_class_id == SubjectClass.id)
        .filter(
            ClassSession.room_id == room_id,
            ClassSession.session_date == exam_date,
            SubjectClass.is_active == True,
        )
        .all()
    )
    for (session,) in class_sessions:
        cs_start, cs_end = _session_time_range(exam_date, session)
        if new_start < cs_end and cs_start < new_end:
            return True

    return check_exam_time_overlap(db, room_id, exam_date, time_frame, duration, exclude_exam_id)


def check_room_conflict_with_candidate_sessions(
        db: Session,
        candidate_sessions: list[dict],
        exclude_subject_class_id: int,
) -> bool:
    for candidate in candidate_sessions:
        session_date = candidate["session_date"]
        room_id = candidate["room_id"]
        session_val = candidate["session"]

        class_conflict = (
            db.query(ClassSession.id)
            .join(SubjectClass, ClassSession.subject_class_id == SubjectClass.id)
            .filter(
                ClassSession.room_id == room_id,
                ClassSession.session_date == session_date,
                ClassSession.session == session_val,
                ClassSession.subject_class_id != exclude_subject_class_id,
                SubjectClass.is_active == True,
            )
            .first()
        )
        if class_conflict:
            return True

        new_start, new_end = _session_time_range(session_date, session_val)
        exams = (
            db.query(Exam.time_frame, Exam.duration)
            .filter(
                Exam.room_id == room_id,
                Exam.exam_date == session_date,
                Exam.status != ExamStatus.CANCELLED,
                Exam.is_active == True,
            )
            .all()
        )
        for time_frame, duration in exams:
            exam_start, exam_end = _exam_time_range(session_date, time_frame, duration)
            if new_start < exam_end and exam_start < new_end:
                return True

    return False


def check_teacher_invigilation_conflict_with_candidate_sessions(
        db: Session,
        teacher_id: int,
        candidate_sessions: list[dict],
) -> bool:
    invigilators = (
        db.query(Exam.exam_date, Exam.time_frame, Exam.duration)
        .join(ExamInvigilator, ExamInvigilator.exam_id == Exam.id)
        .filter(
            ExamInvigilator.teacher_id == teacher_id,
            ExamInvigilator.is_active == True,
            Exam.status != ExamStatus.CANCELLED,
            Exam.is_active == True,
        )
        .all()
    )
    if not invigilators:
        return False

    for candidate in candidate_sessions:
        session_start, session_end = _session_time_range(
            candidate["session_date"], candidate["session"]
        )
        for exam_date, time_frame, duration in invigilators:
            if exam_date != candidate["session_date"]:
                continue
            exam_start, exam_end = _exam_time_range(exam_date, time_frame, duration)
            if session_start < exam_end and exam_start < session_end:
                return True

    return False


def get_exams_invalid_after_candidate_sessions(
        db: Session,
        subject_class_id: int,
        candidate_sessions: list[dict],
) -> list[Exam]:
    if not candidate_sessions:
        return []

    last_session_date = max(c["session_date"] for c in candidate_sessions)

    return (db.query(Exam).filter(
        Exam.subject_class_id == subject_class_id,
        Exam.is_active == True,
        Exam.status != ExamStatus.CANCELLED,
        Exam.exam_date <= last_session_date,
    ).all()
            )


def check_teacher_teaching_conflict_with_exam(
        db: Session,
        teacher_id: int,
        exam_date: date,
        time_frame,
        duration: int,
) -> bool:
    new_start, new_end = _exam_time_range(exam_date, time_frame, duration)

    teaching_sessions = (
        db.query(ClassSession.session)
        .join(TeachingAssignment, TeachingAssignment.subject_class_id == ClassSession.subject_class_id)
        .join(SubjectClass, ClassSession.subject_class_id == SubjectClass.id)
        .filter(
            TeachingAssignment.teacher_id == teacher_id,
            TeachingAssignment.is_active == True,
            ClassSession.session_date == exam_date,
            SubjectClass.is_active == True,
        )
        .all()
    )
    for (session,) in teaching_sessions:
        s_start, s_end = _session_time_range(exam_date, session)
        if new_start < s_end and s_start < new_end:
            return True

    return False
