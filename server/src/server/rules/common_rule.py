from server.models import (
    User,
    Subject,
    SubjectClass,
    Room,
    Exam,
)


def user_exists(db, user_id):
    return db.get(User, user_id) is not None


def subject_exists(db, subject_id):
    return db.get(Subject, subject_id) is not None


def subject_class_exists(db, class_id):
    return db.get(SubjectClass, class_id) is not None


def room_exists(db, room_id):
    return db.get(Room, room_id) is not None


def exam_exists(db, exam_id):
    return db.get(Exam, exam_id) is not None
