from server.models import UserRole


def is_student(user):
    return user.role == UserRole.STUDENT


def is_teacher(user):
    return user.role == UserRole.TEACHER


def is_admin(user):
    return user.role == UserRole.ADMIN
