from sqlalchemy.orm import Session

from server.models import Schedule, SubjectClass, TeachingAssignment


def check_teacher_schedule_conflict(
        db: Session,
        teacher_id,
        subject_class_id,
):
    new_slots = db.query(
        Schedule.weekday,
        Schedule.session,
    ).filter(
        Schedule.subject_class_id == subject_class_id
    ).all()

    existing = set(
        db.query(
            Schedule.weekday,
            Schedule.session,
        )
        .join(
            SubjectClass,
            Schedule.subject_class_id == SubjectClass.id
        )
        .join(
            TeachingAssignment,
            TeachingAssignment.subject_class_id == SubjectClass.id
        )
        .filter(
            TeachingAssignment.teacher_id == teacher_id
        ).all()
    )

    return any(
        slot in existing
        for slot in new_slots
    )


def check_duplicate_teaching_assignment(
        db: Session,
        teacher_id,
        subject_class_id,
):
    return db.query(
        TeachingAssignment.id
    ).filter(
        TeachingAssignment.teacher_id == teacher_id,
        TeachingAssignment.subject_class_id == subject_class_id,
    ).first() is not None
