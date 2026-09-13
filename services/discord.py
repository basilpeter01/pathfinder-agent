import os
import time
import requests
from datetime import datetime
from sqlalchemy.orm import Session
from models.schemas import NotificationDB, OpportunitySchema
from dotenv import load_dotenv
from services.logger import log_event

load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
try:
    DISCORD_SCORE_THRESHOLD = float(os.getenv("DISCORD_SCORE_THRESHOLD", "85"))
except ValueError:
    DISCORD_SCORE_THRESHOLD = 85.0

def _is_webhook_valid() -> bool:
    if not DISCORD_WEBHOOK_URL or DISCORD_WEBHOOK_URL == "your_discord_webhook_url_here" or "your_" in DISCORD_WEBHOOK_URL:
        return False
    return True

def send_agent_run_summary(db: Session, total_evaluated: int, top_opp: OpportunitySchema) -> bool:
    """Send a single summary alert to Discord per agent run."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. Log to SQLite database
    title = f"Scout Run Complete: {total_evaluated} found"
    msg_text = f"Top match: {top_opp.title} at {top_opp.company}"
    db_notif = NotificationDB(
        title=title,
        message=msg_text,
        url=top_opp.url,
        timestamp=timestamp
    )
    db.add(db_notif)
    db.commit()
    log_event("INFO", "DISCORD", f"Logged agent run summary to SQLite")
    
    # 2. Send via Discord Webhook if configured
    if not _is_webhook_valid():
        log_event("INFO", "DISCORD", f"Webhook URL unconfigured. Offline notification persisted to database.")
        return True
        
    try:
        embed = {
            "title": f"Agent Scout Complete",
            "description": f"The agent evaluated **{total_evaluated}** new opportunities.",
            "color": 3066993,
            "fields": [
                {"name": "Top Opportunity", "value": f"[{top_opp.title}]({top_opp.url}) at **{top_opp.company}**", "inline": False},
                {"name": "Relevance Score", "value": f"{top_opp.score}/100", "inline": True}
            ],
            "footer": {"text": f"Pathfinder AI Scout • {timestamp}"}
        }
        
        payload = {
            "username": "Pathfinder AI Scout",
            "avatar_url": "https://img.icons8.com/clouds/200/compass.png",
            "embeds": [embed]
        }
        
        t0 = time.time()
        masked_url = DISCORD_WEBHOOK_URL[:33] + "..." if len(DISCORD_WEBHOOK_URL) > 33 else "Discord Webhook"
        log_event("INFO", "DISCORD", f"Outbound request -> POST {masked_url} | summary")
        res = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        dur = int((time.time() - t0) * 1000)
        if res.status_code in [200, 204]:
            log_event("INFO", "DISCORD", f"Webhook summary sent successfully (HTTP {res.status_code}, {dur}ms)")
            return True
        else:
            log_event("WARNING", "DISCORD", f"Webhook summary failed (HTTP {res.status_code}, {dur}ms) | {res.text[:80]}")
            return False
    except Exception as e:
        log_event("ERROR", "DISCORD", f"Webhook delivery error | error: {e}")
        return False
""" dashboard route /notifications"""
def get_notification_logs(db: Session, limit: int = 50):
    """Retrieve logged system notifications from SQLite."""
    return db.query(NotificationDB).order_by(NotificationDB.id.desc()).limit(limit).all()
