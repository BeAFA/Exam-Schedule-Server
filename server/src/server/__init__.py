import json
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine, Integer, DateTime, func, Boolean, MetaData
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column
from fastapi import FastAPI

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

engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
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
    finally:
        db.close()


app = FastAPI(title="Hệ thống quản lý lịch thi")