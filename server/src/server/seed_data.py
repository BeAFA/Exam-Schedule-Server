"""
Script tạo dữ liệu mẫu cho hệ thống quản lý lịch thi.

LƯU Ý TRƯỚC KHI CHẠY:
- Dòng import session/engine bên dưới là GIẢ ĐỊNH theo pattern phổ biến
  (server/__init__.py export SessionLocal, engine). Nếu project bạn đặt tên
  khác (VD: get_db(), db.session...), chỉnh lại đúng 3 dòng import đầu file.
- Toàn bộ user mẫu dùng chung mật khẩu: "123456" (chỉ để test/demo).
- Thứ tự insert đã được sắp theo đúng phụ thuộc khóa ngoại: User/Subject/Room
  -> SubjectClass -> Schedule/TeachingAssignment/Enrollment -> Exam
  -> ExamInvigilator/ExamRegistration.
"""

from datetime import datetime

from server import Base, engine, SessionLocal
from server.models import (
    User, UserRole,
    Subject,
    SubjectClass, Semester, ClassStatus,
    Room,
    Schedule, Weekday, Session as SessionEnum,
    Exam, TypeOfExam, TimeFrame, ExamStatus,
    ExamInvigilator,
    ExamRegistration, AttendanceStatus,
    Enrollment,
    TeachingAssignment,
)

DEFAULT_PASSWORD = "123456"
ACADEMIC_YEAR = "2025-2026"


def seed():
    Base.metadata.create_all(engine)
    db = SessionLocal()

    try:
        # ================= USERS =================
        # 5 student + 5 teacher + 1 admin
        students_data = [
            ("SV230001", "Nguyen", "Van An", "an.nguyen@student.edu.vn"),
            ("SV230002", "Tran", "Thi Binh", "binh.tran@student.edu.vn"),
            ("SV230003", "Le", "Van Cuong", "cuong.le@student.edu.vn"),
            ("SV230004", "Pham", "Thi Dung", "dung.pham@student.edu.vn"),
            ("SV230005", "Hoang", "Van Em", "em.hoang@student.edu.vn"),
        ]
        teachers_data = [
            ("GV001", "Do", "Thi Hoa", "hoa.do@teacher.edu.vn"),
            ("GV002", "Vu", "Van Khoa", "khoa.vu@teacher.edu.vn"),
            ("GV003", "Bui", "Thi Lan", "lan.bui@teacher.edu.vn"),
            ("GV004", "Dang", "Van Minh", "minh.dang@teacher.edu.vn"),
            ("GV005", "Ngo", "Thi Nga", "nga.ngo@teacher.edu.vn"),
        ]
        admin_data = ("ADM001", "Phan", "Van Quan", "admin@edu.vn")

        students = []
        for code, first, last, email in students_data:
            u = User(user_code=code, first_name=first, last_name=last,
                     email=email, role=UserRole.STUDENT)
            u.set_password(DEFAULT_PASSWORD)
            students.append(u)

        teachers = []
        for code, first, last, email in teachers_data:
            u = User(user_code=code, first_name=first, last_name=last,
                     email=email, role=UserRole.TEACHER)
            u.set_password(DEFAULT_PASSWORD)
            teachers.append(u)

        admin = User(user_code=admin_data[0], first_name=admin_data[1], last_name=admin_data[2],
                     email=admin_data[3], role=UserRole.ADMIN)
        admin.set_password(DEFAULT_PASSWORD)

        db.add_all(students + teachers + [admin])
        db.flush()  # để có user.id dùng cho các bảng sau

        # ================= SUBJECT =================
        subjects_data = [
            ("IT001", "Nhap mon lap trinh", 3),
            ("IT002", "Cau truc du lieu va giai thuat", 4),
            ("IT003", "Co so du lieu", 3),
            ("IT004", "Mang may tinh", 3),
            ("IT005", "He dieu hanh", 3),
            ("IT006", "Lap trinh Web", 3),
        ]
        subjects = [Subject(subject_code=c, name=n, credits=cr) for c, n, cr in subjects_data]
        db.add_all(subjects)
        db.flush()
        subj = {s.subject_code: s for s in subjects}

        # ================= ROOM =================
        rooms_data = [
            ("A101", 50),
            ("A102", 45),
            ("B201", 40),
            ("B202", 40),
            ("C301", 60),
        ]
        rooms = [Room(name=n, capacity=c) for n, c in rooms_data]
        db.add_all(rooms)
        db.flush()
        room = {r.name: r for r in rooms}

        # ================= SUBJECT CLASS =================
        classes_data = [
            # (subject_code, class_name, semester, status, max_students)
            ("IT001", "Lop 01", Semester.Semester_1, ClassStatus.OPEN, 40),
            ("IT001", "Lop 02", Semester.Semester_1, ClassStatus.OPEN, 40),
            ("IT002", "Lop 01", Semester.Semester_1, ClassStatus.CLOSED, 35),
            ("IT003", "Lop 01", Semester.Semester_1, ClassStatus.CLOSED, 35),
            ("IT004", "Lop 01", Semester.Semester_1, ClassStatus.OPEN, 30),
            ("IT005", "Lop 01", Semester.Semester_2, ClassStatus.OPEN, 30),
            ("IT006", "Lop 01", Semester.Semester_2, ClassStatus.OPEN, 30),
            ("IT002", "Lop 02", Semester.Semester_2, ClassStatus.OPEN, 35),
        ]
        classes = []
        for subject_code, name, sem, status, max_std in classes_data:
            sc = SubjectClass(
                subject_id=subj[subject_code].id,
                subject_class_name=name,
                semester=sem,
                academic_year=ACADEMIC_YEAR,
                status=status,
                max_students=max_std,
            )
            classes.append(sc)
        db.add_all(classes)
        db.flush()
        # classes[0..7] tương ứng theo thứ tự khai báo phía trên

        # ================= SCHEDULE (lịch học hàng tuần) =================
        schedules_data = [
            # (class_index, room_name, weekday, session, semester, year)
            (0, "A101", Weekday.MON, SessionEnum.MORNING, Semester.Semester_1, ACADEMIC_YEAR),
            (1, "A102", Weekday.MON, SessionEnum.AFTERNOON, Semester.Semester_1, ACADEMIC_YEAR),
            (2, "B201", Weekday.TUE, SessionEnum.MORNING, Semester.Semester_1, ACADEMIC_YEAR),
            (3, "B202", Weekday.TUE, SessionEnum.AFTERNOON, Semester.Semester_1, ACADEMIC_YEAR),
            (4, "C301", Weekday.WED, SessionEnum.MORNING, Semester.Semester_1, ACADEMIC_YEAR),
            (5, "A101", Weekday.THU, SessionEnum.MORNING, Semester.Semester_2, ACADEMIC_YEAR),
            (6, "A102", Weekday.THU, SessionEnum.AFTERNOON, Semester.Semester_2, ACADEMIC_YEAR),
            (7, "B201", Weekday.FRI, SessionEnum.MORNING, Semester.Semester_2, ACADEMIC_YEAR),
        ]
        schedules = []
        for class_idx, room_name, weekday, sess, sem, year in schedules_data:
            schedules.append(Schedule(
                subject_class_id=classes[class_idx].id,
                room_id=room[room_name].id,
                weekday=weekday,
                session=sess,
                semester=sem,
                academic_year=year,
            ))
        db.add_all(schedules)

        # ================= TEACHING ASSIGNMENT =================
        teaching_data = [
            (0, 0),  # teachers[0] GV001 -> classes[0] IT001-Lop01
            (1, 1),  # GV002 -> IT001-Lop02
            (0, 2),  # GV001 -> IT002-Lop01
            (2, 3),  # GV003 -> IT003-Lop01
            (3, 4),  # GV004 -> IT004-Lop01
            (1, 5),  # GV002 -> IT005-Lop01
            (4, 6),  # GV005 -> IT006-Lop01
            (2, 7),  # GV003 -> IT002-Lop02
        ]
        assignments = [
            TeachingAssignment(teacher_id=teachers[t_idx].id, subject_class_id=classes[c_idx].id)
            for t_idx, c_idx in teaching_data
        ]
        db.add_all(assignments)

        # ================= ENROLLMENT (đăng ký học phần) =================
        enrollment_data = [
            # (student_index, class_index, semester)
            (0, 0, Semester.Semester_1),  # SV001 -> IT001-Lop01
            (0, 2, Semester.Semester_1),  # SV001 -> IT002-Lop01
            (1, 0, Semester.Semester_1),  # SV002 -> IT001-Lop01
            (1, 3, Semester.Semester_1),  # SV002 -> IT003-Lop01
            (2, 1, Semester.Semester_1),  # SV003 -> IT001-Lop02
            (2, 4, Semester.Semester_1),  # SV003 -> IT004-Lop01
            (3, 5, Semester.Semester_2),  # SV004 -> IT005-Lop01
            (3, 6, Semester.Semester_2),  # SV004 -> IT006-Lop01
            (4, 5, Semester.Semester_2),  # SV005 -> IT005-Lop01
            (4, 7, Semester.Semester_2),  # SV005 -> IT002-Lop02
        ]
        enrollments = [
            Enrollment(
                student_id=students[s_idx].id,
                subject_class_id=classes[c_idx].id,
                semester=sem,
                registered_at=datetime(2025, 8, 20, 9, 0, 0),
                academic_year=ACADEMIC_YEAR,
            )
            for s_idx, c_idx, sem in enrollment_data
        ]
        db.add_all(enrollments)
        db.flush()

        # ================= EXAM =================
        exams_data = [
            # (class_index, room_name, exam_date, type, time_frame, semester, duration)
            (0, "A101", datetime(2025, 10, 15), TypeOfExam.MIDTERM, TimeFrame.SHIFT_1, Semester.Semester_1, 60),
            (0, "A101", datetime(2025, 12, 20), TypeOfExam.FINALTEST, TimeFrame.SHIFT_1, Semester.Semester_1, 90),
            (1, "A102", datetime(2025, 10, 16), TypeOfExam.MIDTERM, TimeFrame.SHIFT_2, Semester.Semester_1, 60),
            (2, "B201", datetime(2025, 12, 21), TypeOfExam.FINALTEST, TimeFrame.SHIFT_1, Semester.Semester_1, 90),
            (3, "B202", datetime(2025, 12, 21), TypeOfExam.FINALTEST, TimeFrame.SHIFT_2, Semester.Semester_1, 90),
            (4, "C301", datetime(2025, 10, 17), TypeOfExam.MIDTERM, TimeFrame.SHIFT_3, Semester.Semester_1, 60),
            (5, "A101", datetime(2026, 3, 10), TypeOfExam.MIDTERM, TimeFrame.SHIFT_1, Semester.Semester_2, 60),
            (6, "A102", datetime(2026, 5, 15), TypeOfExam.FINALTEST, TimeFrame.SHIFT_2, Semester.Semester_2, 90),
        ]
        exams = []
        for class_idx, room_name, exam_date, etype, tframe, sem, duration in exams_data:
            exams.append(Exam(
                subject_class_id=classes[class_idx].id,
                room_id=room[room_name].id,
                exam_date=exam_date,
                type=etype,
                time_frame=tframe,
                semester=sem,
                duration=duration,
                status=ExamStatus.SCHEDULED,
            ))
        db.add_all(exams)
        db.flush()

        # ================= EXAM INVIGILATOR =================
        invigilator_data = [
            (0, 1),  # exams[0] <- teachers[1] GV002
            (1, 2),  # exams[1] <- GV003
            (2, 0),  # exams[2] <- GV001
            (3, 3),  # exams[3] <- GV004
            (4, 4),  # exams[4] <- GV005
            (5, 2),  # exams[5] <- GV003
            (6, 0),  # exams[6] <- GV001
            (7, 1),  # exams[7] <- GV002
        ]
        invigilators = [
            ExamInvigilator(exam_id=exams[e_idx].id, teacher_id=teachers[t_idx].id)
            for e_idx, t_idx in invigilator_data
        ]
        db.add_all(invigilators)

        # ================= EXAM REGISTRATION =================
        # (exam_index, student_index, seat_number)
        registration_data = [
            (0, 0, "A01"),  # exams[0] IT001-Lop01 midterm <- SV001
            (0, 1, "A02"),  # <- SV002
            (1, 0, "A01"),  # exams[1] IT001-Lop01 final <- SV001
            (1, 1, "A02"),  # <- SV002
            (2, 2, "A01"),  # exams[2] IT001-Lop02 midterm <- SV003
            (3, 0, "A01"),  # exams[3] IT002-Lop01 final <- SV001
            (4, 1, "A01"),  # exams[4] IT003-Lop01 final <- SV002
            (5, 2, "A01"),  # exams[5] IT004-Lop01 midterm <- SV003
            (6, 3, "A01"),  # exams[6] IT005-Lop01 midterm <- SV004
            (7, 3, "A01"),  # exams[7] IT006-Lop01 final <- SV004
        ]
        registrations = [
            ExamRegistration(
                exam_id=exams[e_idx].id,
                student_id=students[s_idx].id,
                seat_number=seat,
                attendance_status=AttendanceStatus.PRESENT,
            )
            for e_idx, s_idx, seat in registration_data
        ]
        db.add_all(registrations)

        db.commit()

        print("Seed dữ liệu thành công:")
        print(f"  - Users: {len(students) + len(teachers) + 1} "
              f"(5 student, 5 teacher, 1 admin)")
        print(f"  - Subjects: {len(subjects)}")
        print(f"  - Rooms: {len(rooms)}")
        print(f"  - SubjectClasses: {len(classes)}")
        print(f"  - Schedules: {len(schedules)}")
        print(f"  - TeachingAssignments: {len(assignments)}")
        print(f"  - Enrollments: {len(enrollments)}")
        print(f"  - Exams: {len(exams)}")
        print(f"  - ExamInvigilators: {len(invigilators)}")
        print(f"  - ExamRegistrations: {len(registrations)}")
        print(f"  Mat khau mac dinh cho tat ca user: {DEFAULT_PASSWORD}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()