import json
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine, Integer, DateTime, func, Boolean
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


class Base(DeclarativeBase):
    pass


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

def main():
    import uvicorn
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)