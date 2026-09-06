from server.models import Schedule, SubjectClass, TeachingAssignment, ClassSession


def check_teacher_schedule_conflict(db, teacher_id, subject_class_id, exclude_assignment_id=None):
    new_sessions = db.query(ClassSession.session_date, ClassSession.session).filter(
        ClassSession.subject_class_id == subject_class_id
    ).all()

    if not new_sessions:
        return False

    query = (
        db.query(ClassSession.session_date, ClassSession.session)
        .join(TeachingAssignment, TeachingAssignment.subject_class_id == ClassSession.subject_class_id)
        .join(SubjectClass, ClassSession.subject_class_id == SubjectClass.id)
        .filter(
            TeachingAssignment.teacher_id == teacher_id,
            TeachingAssignment.is_active == True,
            ClassSession.subject_class_id != subject_class_id,
            SubjectClass.is_active == True,
        )
    )
    if exclude_assignment_id is not None:
        query = query.filter(TeachingAssignment.id != exclude_assignment_id)

    existing = set(query.all())
    return any(session in existing for session in new_sessions)

def check_teacher_conflict_with_candidate_sessions(
        db, teacher_id, candidate_sessions: list[dict], exclude_subject_class_id: int,
) -> bool:
    """Kiểm tra các buổi học DỰ KIẾN (chưa ghi DB) có trùng với lịch dạy lớp
    khác của giảng viên không. Dùng khi update_subject_class."""
    for candidate in candidate_sessions:
        conflict = (
            db.query(ClassSession.id)
            .join(TeachingAssignment, TeachingAssignment.subject_class_id == ClassSession.subject_class_id)
            .join(SubjectClass, ClassSession.subject_class_id == SubjectClass.id)
            .filter(
                TeachingAssignment.teacher_id == teacher_id,
                TeachingAssignment.is_active == True,
                ClassSession.subject_class_id != exclude_subject_class_id,
                ClassSession.session_date == candidate["session_date"],
                ClassSession.session == candidate["session"],
                SubjectClass.is_active == True,
            )
            .first()
        )
        if conflict:
            return True
    return False


def check_subject_class_has_teacher(db, subject_class_id, exclude_assignment_id=None):
    query = db.query(TeachingAssignment.id).filter(
        TeachingAssignment.subject_class_id == subject_class_id,
        TeachingAssignment.is_active == True,
    )
    if exclude_assignment_id is not None:
        query = query.filter(TeachingAssignment.id != exclude_assignment_id)
    return query.first() is not None
