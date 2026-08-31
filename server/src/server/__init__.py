import json
import re
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine, Integer, DateTime, func, Boolean, MetaData
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column
from fastapi import FastAPI
import cloudinary
import cloudinary.uploader
import cloudinary.api

cloudinary.config(secure=True)

BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_PATH = BASE_DIR / "credentials" / "database.json"

try:
    with open(CREDENTIALS_PATH, encoding="utf-8") as json_file:
        config = json.load(json_file)
    DATABASE_URL = config["DATABASE_URL"]
except FileNotFoundError:
    raise RuntimeError(f"Không tìm thấy file credentials tại: {CREDENTIALS_PATH}")
except KeyError:
    raise RuntimeError("File database.json thiếu key 'DATABASE_URL'")

CLOUDINARY_API_KEY = config["CLOUDINARY_API_KEY"]
CLOUDINARY_API_SECRET = config["CLOUDINARY_API_SECRET"]
CLOUDINARY_CLOUD_NAME = config["CLOUDINARY_CLOUD_NAME"]

cloudinary.config(
    cloud_name=config["CLOUDINARY_CLOUD_NAME"],
    api_key=config["CLOUDINARY_API_KEY"],
    api_secret=config["CLOUDINARY_API_SECRET"],
)


def uploadImage(file):
    result = cloudinary.uploader.upload(file)
    return result["secure_url"]


def extract_public_id(img_url: str) -> str | None:
    match = re.search(r"/upload/(?:v\d+/)?(.+)\.\w+$", img_url)
    return match.group(1) if match else None


def destroyImage(img_url: str) -> bool:
    public_id = extract_public_id(img_url)
    if not public_id:
        return False
    result = cloudinary.uploader.destroy(public_id)
    return result.get("result") == "ok"


engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
    connect_args={
        "init_command": "SET SESSION innodb_lock_wait_timeout = 5"
    },
    echo=config.get("DEBUG", False),
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=naming_convention)


class Classify:
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


app = FastAPI(title="Hệ thống quản lý lịch thi")
