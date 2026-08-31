from server.models import Schedule, SubjectClass, TeachingAssignment, ClassSession


def check_teacher_schedule_conflict(db, teacher_id, subject_class_id, exclude_assignment_id=None):
    """Kiểm tra giảng viên có buổi dạy thực tế (ClassSession) trùng ngày + buổi với lớp khác
    mà giảng viên này đang phụ trách hay không."""
    new_sessions = db.query(ClassSession.session_date, ClassSession.session).filter(
        ClassSession.subject_class_id == subject_class_id
    ).all()

    if not new_sessions:
        return False

    query = (
        db.query(ClassSession.session_date, ClassSession.session)
        .join(TeachingAssignment, TeachingAssignment.subject_class_id == ClassSession.subject_class_id)
        .filter(
            TeachingAssignment.teacher_id == teacher_id,
            ClassSession.subject_class_id != subject_class_id,
            SubjectClass.is_active == True,
        )
    )
    if exclude_assignment_id is not None:
        query = query.filter(TeachingAssignment.id != exclude_assignment_id)

    existing = set(query.all())
    return any(session in existing for session in new_sessions)


def check_subject_class_has_teacher(db, subject_class_id, exclude_assignment_id=None):
    """Lớp học phần chỉ được phép có 1 giảng viên phụ trách (ràng buộc uq_subject_class_teacher)."""
    query = db.query(TeachingAssignment.id).filter(
        TeachingAssignment.subject_class_id == subject_class_id
    )
    if exclude_assignment_id is not None:
        query = query.filter(TeachingAssignment.id != exclude_assignment_id)
    return query.first() is not None
