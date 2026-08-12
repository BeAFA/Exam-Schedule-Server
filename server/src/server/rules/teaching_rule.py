from sqlalchemy.orm import Session

from server.models import Schedule, SubjectClass, TeachingAssignment


def check_teacher_schedule_conflict(db, teacher_id, subject_class_id, exclude_assignment_id=None):
    new_slots = db.query(Schedule.weekday, Schedule.session).filter(
        Schedule.subject_class_id == subject_class_id
    ).all()

    query = (
        db.query(Schedule.weekday, Schedule.session)
        .join(SubjectClass, Schedule.subject_class_id == SubjectClass.id)
        .join(TeachingAssignment, TeachingAssignment.subject_class_id == SubjectClass.id)
        .filter(TeachingAssignment.teacher_id == teacher_id)
    )
    if exclude_assignment_id is not None:
        query = query.filter(TeachingAssignment.id != exclude_assignment_id)

    existing = set(query.all())
    return any(slot in existing for slot in new_slots)


def check_duplicate_teaching_assignment(db, teacher_id, subject_class_id, exclude_assignment_id=None):
    query = db.query(TeachingAssignment.id).filter(
        TeachingAssignment.teacher_id == teacher_id,
        TeachingAssignment.subject_class_id == subject_class_id,
    )
    if exclude_assignment_id is not None:
        query = query.filter(TeachingAssignment.id != exclude_assignment_id)
    return query.first() is not None
