from sqlalchemy.orm import Session

from server.models import Schedule, SubjectClass, TeachingAssignment


def check_teacher_schedule_conflict(db, teacher_id, subject_class_id, exclude_assignment_id=None):
    """Kiểm tra giảng viên có bị trùng thứ/buổi giảng dạy với lớp khác không,
    chỉ so trong CÙNG học kỳ + năm học của lớp đang xét (khác học kỳ thì không tính là trùng)."""
    target = db.get(SubjectClass, subject_class_id)
    if target is None:
        return False

    new_slots = db.query(Schedule.weekday, Schedule.session).filter(
        Schedule.subject_class_id == subject_class_id
    ).all()

    query = (
        db.query(Schedule.weekday, Schedule.session)
        .join(SubjectClass, Schedule.subject_class_id == SubjectClass.id)
        .join(TeachingAssignment, TeachingAssignment.subject_class_id == SubjectClass.id)
        .filter(
            TeachingAssignment.teacher_id == teacher_id,
            SubjectClass.semester == target.semester,
            SubjectClass.academic_year == target.academic_year,
            SubjectClass.id != subject_class_id,
        )
    )
    if exclude_assignment_id is not None:
        query = query.filter(TeachingAssignment.id != exclude_assignment_id)

    existing = set(query.all())
    return any(slot in existing for slot in new_slots)


def check_duplicate_teaching_assignment(db, teacher_id, subject_class_id, exclude_assignment_id=None):
    """Giảng viên này đã được phân công đúng lớp này chưa.
    Lưu ý: model hiện chỉ cho phép 1 lớp có DUY NHẤT 1 phân công (uq_subject_class_teacher),
    nên nên ưu tiên dùng check_subject_class_has_teacher bên dưới; hàm này giữ lại cho
    trường hợp so khớp cụ thể giảng viên + lớp."""
    query = db.query(TeachingAssignment.id).filter(
        TeachingAssignment.teacher_id == teacher_id,
        TeachingAssignment.subject_class_id == subject_class_id,
    )
    if exclude_assignment_id is not None:
        query = query.filter(TeachingAssignment.id != exclude_assignment_id)
    return query.first() is not None


def check_subject_class_has_teacher(db, subject_class_id, exclude_assignment_id=None):
    """Lớp học phần chỉ được phép có 1 giảng viên phụ trách (ràng buộc uq_subject_class_teacher)."""
    query = db.query(TeachingAssignment.id).filter(
        TeachingAssignment.subject_class_id == subject_class_id
    )
    if exclude_assignment_id is not None:
        query = query.filter(TeachingAssignment.id != exclude_assignment_id)
    return query.first() is not None