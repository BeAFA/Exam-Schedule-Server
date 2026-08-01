from sqlalchemy.orm import Session

from server.models import ExamRegistration, Exam, ExamInvigilator, ExamStatus


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
