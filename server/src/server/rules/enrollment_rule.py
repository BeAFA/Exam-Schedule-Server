from sqlalchemy import func, select, exists
from sqlalchemy.orm import Session

from server.models import Enrollment, Subject, SubjectClass, Schedule, ClassStatus, Semester

MAXIMUM_CREDITS = 21


def check_duplicate_enrollment(
        db: Session,
        student_id,
        subject_class_id,
):
    stmt = select(exists().where(Enrollment.student_id == student_id,
                                 Enrollment.subject_class_id == subject_class_id))
    return db.scalar(stmt)


def check_credit_limit(
        db: Session,
        student_id,
        subject_class,
):
    stmt = select(func.coalesce(func.sum(Subject.credits), 0)).join(SubjectClass,
            Subject.id == SubjectClass.subject_id).join(Enrollment,
            Enrollment.subject_class_id == SubjectClass.id).where(Enrollment.student_id == student_id,
            SubjectClass.semester == subject_class.semester,
            SubjectClass.academic_year == subject_class.academic_year)

    return db.scalar(stmt) + subject_class.subject.credits <= MAXIMUM_CREDITS


def check_schedule_conflict(
        db: Session,
        student_id: int,
        subject_class_id: int,
        semester: Semester,
        academic_year: str,
) -> bool:
    existing_slots = set(
        db.query(
            Schedule.weekday, Schedule.session
        )
        .join(
            SubjectClass, Schedule.subject_class_id == SubjectClass.id
        )
        .join(
            Enrollment, Enrollment.subject_class_id == SubjectClass.id
        )
        .filter(
            Enrollment.student_id == student_id,
            SubjectClass.semester == semester,
            SubjectClass.academic_year == academic_year,
        )
        .all()
    )

    new_slots = db.query(
        Schedule.weekday, Schedule.session
    ).filter(
        Schedule.subject_class_id == subject_class_id
    ).all()

    return any(
        slot in existing_slots for slot in new_slots
    )


def check_subject_class_capacity(db: Session, subject_class):
    current = db.query(
        Enrollment.id
    ).filter(
        Enrollment.subject_class_id == subject_class.id
    ).count()

    return current < subject_class.max_students


def check_subject_class_status(subject_class):
    return subject_class.status == ClassStatus.OPEN