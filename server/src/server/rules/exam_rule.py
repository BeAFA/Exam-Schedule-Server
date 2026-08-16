from datetime import datetime, timedelta, date, time

from sqlalchemy import func
from sqlalchemy.orm import Session

from server.models import (
    ExamRegistration, Exam, ExamInvigilator, ExamStatus, Schedule, SubjectClass, ClassSession, SessionEN,
    TeachingAssignment, WEEKDAY_TO_PYTHON,
)

PYTHON_TO_WEEKDAY = {v: k for k, v in WEEKDAY_TO_PYTHON.items()}

SESSION_TIME_RANGE = {
    SessionEN.MORNING: (time(7, 0), time(11, 30)),
    SessionEN.AFTERNOON: (time(13, 0), time(17, 30)),
}


def check_duplicate_exam_registration(db: Session, student_id, exam_id):
    return db.query(ExamRegistration.id).filter(
        ExamRegistration.student_id == student_id,
        ExamRegistration.exam_id == exam_id,
    ).first() is not None


def check_exam_schedule_conflict(db: Session, student_id: int, exam_id: int) -> bool:
    new_exam = db.query(Exam.exam_date, Exam.time_frame).filter(Exam.id == exam_id).first()

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
    registered = db.query(ExamRegistration.id).filter(ExamRegistration.exam_id == exam.id).count()
    return registered < exam.room.capacity


def check_exam_status(exam):
    return exam.status == ExamStatus.SCHEDULED


def check_invigilator_conflict(
        db: Session,
        teacher_id: int,
        exam_date: date,
        time_frame,
        exclude_exam_id: int = None,
        exclude_invigilator_id: int = None,
) -> bool:
    """
    exclude_exam_id: loại trừ theo Exam.id (dùng khi kiểm tra "giáo viên đang coi thi ca X
    có còn rảnh không nếu ca X đổi ngày/giờ" — tự nhiên phải loại trừ chính ca X).
    exclude_invigilator_id: loại trừ theo ExamInvigilator.id (dùng khi đổi giáo viên coi thi
    cho MỘT bản ghi phân công cụ thể, exam_id không đổi).
    """
    query = (
        db.query(ExamInvigilator.id)
        .join(Exam, ExamInvigilator.exam_id == Exam.id)
        .filter(
            ExamInvigilator.teacher_id == teacher_id,
            Exam.exam_date == exam_date,
            Exam.time_frame == time_frame,
        )
    )
    if exclude_exam_id is not None:
        query = query.filter(Exam.id != exclude_exam_id)
    if exclude_invigilator_id is not None:
        query = query.filter(ExamInvigilator.id != exclude_invigilator_id)
    return query.first() is not None


def check_duplicate_exam_invigilator(
        db: Session,
        exam_id: int,
        teacher_id: int,
        exclude_id: int = None,
) -> bool:
    """Giáo viên này đã được phân công coi thi đúng ca thi (exam_id) này chưa (ứng với uq_exam_teacher)."""
    query = db.query(ExamInvigilator.id).filter(
        ExamInvigilator.exam_id == exam_id,
        ExamInvigilator.teacher_id == teacher_id,
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
        )
    )

    if exclude_subject_class_id is not None:
        query = query.filter(Schedule.subject_class_id != exclude_subject_class_id)

    return query.first() is not None


def get_last_class_session_date(db: Session, subject_class_id: int) -> date | None:
    """Lấy ngày của buổi học cuối cùng của lớp học phần để xếp lịch thi sau đó."""
    last_session = (
        db.query(ClassSession.session_date)
        .join(Schedule, ClassSession.schedule_id == Schedule.id)
        .filter(Schedule.subject_class_id == subject_class_id)
        .order_by(ClassSession.session_date.desc())
        .first()
    )
    return last_session[0] if last_session else None


def check_exam_date_after_last_session(db: Session, subject_class_id: int, exam_date: date) -> bool:
    """Kiểm tra ngày thi có diễn ra SAU buổi học cuối cùng không."""
    last_date = get_last_class_session_date(db, subject_class_id)
    if not last_date:
        return True  # Lớp chưa có lịch trình thì bỏ qua
    return exam_date > last_date


def check_exam_conflict_with_regular_class(db: Session, subject_class_id: int, exam_date: date) -> bool:
    """Đảm bảo ngày thi (tùy chọn) không rơi trúng vào ngày mà chính sinh viên lớp đó đang có buổi học."""
    conflict = (
        db.query(ClassSession.id)
        .join(Schedule, ClassSession.schedule_id == Schedule.id)
        .filter(
            Schedule.subject_class_id == subject_class_id,
            ClassSession.session_date == exam_date
        )
        .first()
    )
    return conflict is not None


def check_room_used_by_class_session(db: Session, room_id: int, exam_date: date) -> bool:
    """Vì ClassSession.session_date và exam_date đều đã là Date, có thể so sánh trực tiếp"""
    return (
        db.query(ClassSession.id)
        .join(Schedule, ClassSession.schedule_id == Schedule.id)
        .filter(
            Schedule.room_id == room_id,
            ClassSession.session_date == exam_date,
        )
        .first()
    ) is not None


def _exam_time_range(exam_date: date, time_frame, duration: int):
    """Combine trực tiếp với đối tượng date"""
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
    """
    Kiểm tra khoảng thời gian thi thực tế (tính từ time_frame + duration) có bị đụng với:
    - Buổi học thường (ClassSession) diễn ra trong phòng này, cùng ngày, hoặc
    - Ca thi (Exam) khác đã xếp trong cùng phòng, cùng ngày
    So theo khoảng giờ bắt đầu/kết thúc thực tế, không chỉ so ngày như check_room_used_by_class_session.
    """
    new_start, new_end = _exam_time_range(exam_date, time_frame, duration)

    # 1. Đụng với buổi học thường (ClassSession) trong phòng, cùng ngày
    class_sessions = (
        db.query(ClassSession.session)
        .join(Schedule, ClassSession.schedule_id == Schedule.id)
        .filter(
            Schedule.room_id == room_id,
            ClassSession.session_date == exam_date,
        )
        .all()
    )
    for (session,) in class_sessions:
        cs_start, cs_end = _session_time_range(exam_date, session)
        if new_start < cs_end and cs_start < new_end:
            return True

    # 2. Đụng với ca thi (Exam) khác trong cùng phòng, cùng ngày
    return check_exam_time_overlap(db, room_id, exam_date, time_frame, duration, exclude_exam_id)


def check_teacher_teaching_conflict_with_exam(
        db: Session,
        teacher_id: int,
        exam_date: date,
        time_frame,
        duration: int,
) -> bool:
    """
    Kiểm tra giáo viên có đang có lịch giảng dạy cố định (TeachingAssignment + Schedule,
    theo thứ trong tuần + buổi sáng/chiều) trùng với khoảng thời gian thực tế của ca thi
    (suy ra từ exam_date -> thứ trong tuần, và time_frame + duration -> khoảng giờ thực tế) hay không.

    Lưu ý: nếu ca thi rơi vào khung giờ không thuộc SESSION_TIME_RANGE nào (VD: ca tối SHIFT_5),
    hàm sẽ không tìm thấy xung đột nào với lịch dạy — vì lịch dạy chỉ tồn tại ở buổi sáng/chiều.
    """
    weekday = PYTHON_TO_WEEKDAY.get(exam_date.weekday())
    if weekday is None:
        return False

    new_start, new_end = _exam_time_range(exam_date, time_frame, duration)

    teaching_sessions = (
        db.query(Schedule.session)
        .join(TeachingAssignment, TeachingAssignment.subject_class_id == Schedule.subject_class_id)
        .filter(
            TeachingAssignment.teacher_id == teacher_id,
            Schedule.weekday == weekday,
        )
        .all()
    )
    for (session,) in teaching_sessions:
        s_start, s_end = _session_time_range(exam_date, session)
        if new_start < s_end and s_start < new_end:
            return True

    return False