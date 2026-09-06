from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler

from server import SessionLocal
from server.crud import clear_expired_blacklist

scheduler = BackgroundScheduler()


def cleanup_blacklist():
    db = SessionLocal()
    try:
        clear_expired_blacklist(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def start_scheduler():
    scheduler.add_job(
        cleanup_blacklist,
        trigger="interval",
        days=1,
        id="clear_expired_blacklist",
        replace_existing=True,
        next_run_time=datetime.now(timezone.utc)
    )
    scheduler.start()
