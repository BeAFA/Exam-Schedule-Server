# Exam Schedule Server

Backend API cho hệ thống quản lý lớp học phần và lịch thi của trường đại học. Dự án được xây dựng bằng FastAPI, SQLAlchemy và MySQL, tập trung vào việc quản lý môn học, lớp học, lịch học, lịch thi, giảng viên coi thi và phân quyền người dùng.

## Tổng quan

Hệ thống này hỗ trợ các chức năng chính sau:

- Quản lý người dùng theo vai trò: Admin, Teacher, Student
- Quản lý môn học, lớp học phần và phòng học
- Thiết lập lịch học theo tuần và sinh dữ liệu buổi học tự động
- Quản lý đề thi, thời gian thi và phòng thi
- Phân công giảng viên giảng dạy và coi thi
- Kiểm tra xung đột lịch, phòng học, giảng viên và thời gian thi
- Xác thực và phân quyền JWT
- Upload ảnh đại diện lên Cloudinary
- Chạy nền với APScheduler

## Công nghệ sử dụng

- Python 3.14+
- FastAPI
- SQLAlchemy 2.x
- MySQL / MariaDB
- Alembic (migration database)
- Pydantic v2
- JWT (python-jose)
- APScheduler
- Cloudinary
- Uvicorn

## Cấu trúc repository

```text
Exam-Schedule-Server/
├── LICENSE
├── README.md
├── server/
│   ├── README.md
│   ├── alembic.ini
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── .python-version
│   └── src/
│       └── server/
│           ├── __init__.py
│           ├── auth.py
│           ├── crud.py
│           ├── daily_task.py
│           ├── exceptions.py
│           ├── main.py
│           ├── models.py
│           ├── schemas.py
│           ├── seed_data.py
│           ├── rules/
│           │   ├── exam_rule.py
│           │   ├── subject_class_rule.py
│           │   └── teaching_rule.py
│           ├── static/
│           └── credentials/   # được tạo khi setup local
└──
```

## Mô tả các module chính

- `server/src/server/main.py`: khởi tạo FastAPI app và định nghĩa API endpoints chính
- `server/src/server/models.py`: định nghĩa schema dữ liệu, enum, quan hệ ORM và logic tạo lịch học
- `server/src/server/crud.py`: xử lý logic nghiệp vụ CRUD và kiểm tra ràng buộc
- `server/src/server/schemas.py`: Pydantic schema cho request/response
- `server/src/server/auth.py`: xác thực JWT, kiểm tra quyền truy cập
- `server/src/server/rules/`: các hàm kiểm tra xung đột lịch học và lịch thi
- `server/src/server/seed_data.py`: tạo dữ liệu mẫu để thử nghiệm
- `server/src/server/daily_task.py`: scheduler chạy nền
- `server/src/server/__init__.py`: kết nối database, cấu hình Cloudinary, khởi tạo app

## Quy trình nghiệp vụ chính

### 1. Quản lý người dùng
- Người dùng đăng nhập qua endpoint `/login`
- Token JWT được cấp theo email và role
- Một số API chỉ dành cho Admin hoặc Teacher

### 2. Quản lý môn học và lớp học phần
- Admin có thể tạo, cập nhật và tắt/bật lớp học phần
- Hệ thống lưu thông tin môn học, kỳ học, năm học, số tiết, phòng học, lịch học định kỳ

### 3. Tự động sinh lịch học
- Mỗi `SubjectClass` có `Schedule` theo từng thứ và buổi
- Hệ thống sinh `ClassSession` tự động dựa trên lịch học và ngày bắt đầu
- Dữ liệu này được dùng để kiểm tra thời gian học và phòng học

### 4. Quản lý lịch thi
- Hệ thống cho phép lập lịch thi cho từng lớp học phần
- Kiểm tra xung đột phòng thi, thời gian thi, và giảng viên coi thi
- Hỗ trợ trạng thái: `SCHEDULED`, `FINISHED`, `CANCELLED`

### 5. Phân công giảng viên
- Một giảng viên có thể được gán làm giảng viên chính của một lớp học phần
- Một hoặc nhiều giảng viên có thể coi thi cho một buổi thi

## API chính

Một số endpoint quan trọng trong hệ thống:

- `POST /login` - đăng nhập
- `POST /logout` - đăng xuất
- `GET /me` - thông tin người dùng hiện tại
- `GET /subject` - danh sách môn học
- `GET /room` - danh sách phòng học
- `GET /schedule` - lịch học
- `GET /subject_class` - danh sách lớp học phần
- `POST /subject_class/create` - tạo lớp học phần
- `POST /subject_class/{id}/update` - cập nhật lớp học phần
- `GET /teacher` - danh sách giảng viên
- `GET /exam` - danh sách lịch thi
- `POST /exam/create` - tạo lịch thi
- `POST /exam/{id}/update` - cập nhật lịch thi
- `GET /exam_invigilator` - danh sách coi thi
- `POST /exam_invigilator/set` - thiết lập coi thi

## Cài đặt và chạy dự án

### Yêu cầu

- Python 3.14
- MySQL hoặc MariaDB
- `uv` (khuyến nghị) hoặc `pip`

### Bước 1: Cài đặt dependencies

Tại thư mục `server`:

```bash
cd server
uv sync
```

Nếu không dùng `uv`:

```bash
cd server
pip install -r src/server/requirements.txt
```

### Bước 2: Cấu hình database và Cloudinary

Tạo file:

```text
server/src/server/credentials/database.json
```

Với nội dung ví dụ:

```json
{
  "DATABASE_URL": "mysql+pymysql://username:password@localhost:3306/exam_schedule_db?charset=utf8mb4",
  "CLOUDINARY_CLOUD_NAME": "your_cloud_name",
  "CLOUDINARY_API_KEY": "your_api_key",
  "CLOUDINARY_API_SECRET": "your_api_secret",
  "DEBUG": false
}
```

> File này là bắt buộc vì ứng dụng đọc cấu hình database và Cloudinary từ đây khi khởi động.

### Bước 3: Tạo schema database

```bash
cd server
alembic upgrade head
```

Hoặc nếu ứng dụng chưa dùng migration:

```bash
python -c "from server import Base, engine; Base.metadata.create_all(engine)"
```

### Bước 4: Chạy server

```bash
cd server
uv run uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
```

Hoặc:

```bash
cd server
python -m uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
```

## Seed dữ liệu mẫu

Để tạo dữ liệu demo cho hệ thống (người dùng, môn học, lớp học, lịch học, lịch thi):

```bash
cd server
uv run python -c "from server.seed_data import seed; seed()"
```

Dữ liệu mẫu được tạo bao gồm:

- 5 sinh viên
- 5 giảng viên
- 1 admin
- 6 môn học
- 8 lớp học phần
- lịch học, lịch thi, phân công giảng dạy và coi thi
- mật khẩu mặc định: `123456`

## Mật khẩu mẫu

Mọi tài khoản trong dữ liệu seed đều dùng cùng mật khẩu mặc định:

```text
123456
```

## Lưu ý

- Dự án đang tập trung vào backend API, không phải giao diện frontend.
- Tương tác thông thường với hệ thống là thông qua API client hoặc frontend ứng dụng tích hợp.
- Một số nghiệp vụ liên quan đến kiểm tra xung đột lịch rất quan trọng và được xử lý ở tầng `rules/`.

## Giấy phép

Dự án này được cấp phép theo giấy phép MIT. Xem file `LICENSE` để biết thêm chi tiết.

## Tác giả

- BeAFA

## Mục tiêu của dự án

Dự án này nhằm xây dựng một hệ thống backend quản lý lớp học phần và lịch thi hiệu quả, hỗ trợ theo dõi lịch học, lịch thi, giảng viên, room, và các ràng buộc nghiệp vụ nhằm tránh xung đột khi lên lịch.

---
