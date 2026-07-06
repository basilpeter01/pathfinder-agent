import os
from apscheduler.schedulers.background import BackgroundScheduler
from memory.sqlite import SessionLocal
from services.opportunities import run_opportunity_scout_pipeline
from dotenv import load_dotenv

load_dotenv()

SCOUT_INTERVAL_MINUTES = int(os.getenv("SCOUT_INTERVAL_MINUTES", "5"))

scheduler = BackgroundScheduler()
_is_running = False

def scheduled_scout_job():
    """Background cron job: open DB session, run scout pipeline, send alerts & log."""
    print(f"[APScheduler] Running background opportunity scout job...")
    db = SessionLocal()
    try:
        opps = run_opportunity_scout_pipeline(db)
        print(f"[APScheduler] Scout completed. Evaluated {len(opps)} opportunities.")
    except Exception as e:
        print(f"[APScheduler Error] Scout job failed: {e}")
    finally:
        db.close()

def start_scheduler():
    """Start APScheduler background loop."""
    global _is_running
    if not _is_running and not scheduler.running:
        scheduler.add_job(
            scheduled_scout_job,
            "interval",
            minutes=SCOUT_INTERVAL_MINUTES,
            id="scout_job",
            replace_existing=True
        )
        scheduler.start()
        _is_running = True
        print(f"[APScheduler] Started background job loop (Interval: {SCOUT_INTERVAL_MINUTES} mins)")

def stop_scheduler():
    """Shutdown APScheduler background loop."""
    global _is_running
    if scheduler.running:
        scheduler.shutdown(wait=False)
        _is_running = False
        print("[APScheduler] Stopped background job loop.")

def get_scheduler_status() -> dict:
    """Return status of background scheduler."""
    return {
        "is_running": _is_running or scheduler.running,
        "interval_minutes": SCOUT_INTERVAL_MINUTES,
        "job_count": len(scheduler.get_jobs()) if scheduler.running else 0
    }
