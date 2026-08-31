from server.models import SubjectClass


def check_subject_class_identity_conflict(
    db, subject_id, subject_class_name, semester, academic_year,
    exclude_subject_class_id: int | None = None,
) -> bool:
    """Thay thế uq_class_identity — chỉ tính các lớp đang is_active=True."""
    query = db.query(SubjectClass.id).filter(
        SubjectClass.subject_id == subject_id,
        SubjectClass.subject_class_name == subject_class_name,
        SubjectClass.semester == semester,
        SubjectClass.academic_year == academic_year,
        SubjectClass.is_active == True,
    )
    if exclude_subject_class_id is not None:
        query = query.filter(SubjectClass.id != exclude_subject_class_id)
    return query.first() is not None

def check_max_students_positive(max_students: int) -> bool:
    return max_students > 0

def check_room_capacity(max_students: int, room_capacity: int) -> bool:
    return max_students <= room_capacity

def check_number_of_sessions_positive(number_of_sessions: int) -> bool:
    return number_of_sessions > 0