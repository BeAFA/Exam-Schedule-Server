# Exam Schedule Server

Backend API cho hệ thống quản lý lớp học phần và lịch thi.

## Mô tả

Dự án này cung cấp API xử lý các chức năng liên quan đến:

- quản lý người dùng theo vai trò Admin / Teacher / Student
- quản lý môn học, lớp học phần, phòng học
- thiết lập lịch học và sinh buổi học tự động
- quản lý lịch thi và phân công coi thi
- kiểm tra xung đột lịch, thời gian, phòng và giảng viên
- xác thực JWT và phân quyền truy cập
- upload avatar lên Cloudinary

## Stack

- Python 3.14+
- FastAPI
- SQLAlchemy
- MySQL
- Alembic
- Pydantic
- JWT
- APScheduler
- Cloudinary

## Cấu trúc thư mục

```text
src/server/
├── __init__.py
├── auth.py
├── crud.py
├── daily_task.py
├── exceptions.py
├── main.py
├── models.py
├── schemas.py
├── seed_data.py
├── rules/
│   ├── exam_rule.py
│   ├── subject_class_rule.py
│   └── teaching_rule.py
├── static/
└── credentials/
```

## Setup

1. Tạo môi trường ảo và cài dependencies

```bash
cd server
uv sync
```

2. Tạo file cấu hình:

```json
{
  "DATABASE_URL": "mysql+pymysql://user:password@localhost:3306/exam_schedule_db?charset=utf8mb4",
  "CLOUDINARY_CLOUD_NAME": "your_cloud_name",
  "CLOUDINARY_API_KEY": "your_api_key",
  "CLOUDINARY_API_SECRET": "your_api_secret",
  "DEBUG": false
}
```

File nên được đặt tại:

```text
server/src/server/credentials/database.json
```

3. Chạy server:

```bash
cd server
uv run uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
```

## Seed dữ liệu

```bash
cd server
uv run python -c "from server.seed_data import seed; seed()"
```

Mật khẩu mặc định cho dữ liệu mẫu:

```text
123456
```

## API nổi bật

- `POST /login`
- `GET /me`
- `GET /subject`
- `GET /room`
- `GET /schedule`
- `GET /subject_class`
- `GET /exam`
- `POST /exam/create`
- `POST /exam_invigilator/set`

## License

MIT License. Xem file `LICENSE`.
