from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError

CONSTRAINT_MESSAGES: dict[str, str] = {
    "uq_class_identity": "Lớp học phần này đã tồn tại (trùng môn học/tên lớp/học kỳ/năm học).",
    "uq_room_datetime": "Phòng đã có lịch thi trùng ngày/giờ này.",
    "uq_class_session_number": "Lớp học phần này đã bị đụng lịch học",
    "uq_subject_class_weekday_session":"Lớp học phần này đã trùng lịch học trong tuần",
    "uq_exam_teacher": "Giảng viên đã được phân công coi ca thi này rồi.",
    "uq_exam_student": "Sinh viên đã đăng ký ca thi này rồi.",
    "uq_exam_seat": "Số ghế này đã có người ngồi trong ca thi.",
    "uq_student_subject_class": "Bạn đã đăng ký lớp học phần này trong học kỳ/năm học này rồi.",
    "uq_teacher_class": "Giảng viên đã được phân công dạy lớp này rồi.",
    "uq_users_email": "Email này đã được sử dụng.",
    "uq_users_user_code": "Mã người dùng này đã tồn tại.",
    "uq_subjects_subject_code": "Mã môn học này đã tồn tại.",
}

DEFAULT_MESSAGE = "Dữ liệu bị trùng lặp hoặc vi phạm ràng buộc dữ liệu, vui lòng kiểm tra lại."

MYSQL_LOCK_TIMEOUT_CODE = 1205

MYSQL_DEADLOCK_CODE = 1213


def _extract_constraint_name(error: IntegrityError) -> str | None:
    msg = str(getattr(error, "orig", error))
    for name in CONSTRAINT_MESSAGES:
        if name in msg:
            return name
    return None


def _extract_mysql_error_code(error: OperationalError) -> int | None:
    orig_args = getattr(error.orig, "args", ())
    return orig_args[0] if orig_args else None


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        constraint = _extract_constraint_name(exc)
        message = CONSTRAINT_MESSAGES.get(constraint, DEFAULT_MESSAGE)
        return JSONResponse(
            status_code=409,
            content={"error": "CONFLICT", "detail": message},
        )

    @app.exception_handler(OperationalError)
    async def operational_error_handler(request: Request, exc: OperationalError):
        error_code = _extract_mysql_error_code(exc)

        if error_code in (MYSQL_LOCK_TIMEOUT_CODE, MYSQL_DEADLOCK_CODE):
            return JSONResponse(
                status_code=503,
                content={
                    "error": "SERVICE_BUSY",
                    "detail": "Hệ thống đang xử lý nhiều yêu cầu, vui lòng thử lại sau ít giây.",
                },
            )

        return JSONResponse(
            status_code=500,
            content={"error": "INTERNAL_ERROR", "detail": "Đã có lỗi xảy ra, vui lòng thử lại."},
        )
