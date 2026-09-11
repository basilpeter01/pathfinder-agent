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

def send_discord_notification(db: Session, opp: OpportunitySchema) -> bool:
    """Send alert to Discord webhook if score > threshold, and log notification in SQLite DB."""
    if opp.score < DISCORD_SCORE_THRESHOLD:
        return False
        
    title = opp.title
    company = opp.company
    score = opp.score
    reason = opp.reason
    url = opp.url
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. Log to SQLite database
    msg_text = f"High-impact opportunity found ({score}/100): {title} at {company}. Reason: {reason}"
    db_notif = NotificationDB(
        title=f"New Opportunity Alert: {company}",
        message=msg_text,
        url=url,
        timestamp=timestamp
    )
    db.add(db_notif)
    db.commit()
    log_event("INFO", "DISCORD", f"Logged opportunity alert to SQLite | '{title[:35]}' at {company} (Score: {score})")
    
    # 2. Send via Discord Webhook if configured
    if not _is_webhook_valid():
        log_event("INFO", "DISCORD", f"Webhook URL unconfigured. Offline notification persisted to database.")
        return True
        
    try:
        embed = {
            "title": f"New High-Impact Internship / Capstone Found!",
            "description": f"**[{title}]({url})** at **{company}**",
            "color": 3066993,
            "fields": [
                {"name": "Relevance Score", "value": f"**{score} / 100**", "inline": True},
                {"name": "Deadline", "value": f"`{opp.deadline}`", "inline": True},
                {"name": "Gemini Reasoning", "value": reason, "inline": False}
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
        log_event("INFO", "DISCORD", f"Outbound request -> POST {masked_url} | item: '{title[:30]}'")
        res = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        dur = int((time.time() - t0) * 1000)
        if res.status_code in [200, 204]:
            log_event("INFO", "DISCORD", f"Webhook notification sent successfully (HTTP {res.status_code}, {dur}ms)")
            return True
        else:
            log_event("WARNING", "DISCORD", f"Webhook notification failed (HTTP {res.status_code}, {dur}ms) | {res.text[:80]}")
            return False
    except Exception as e:
        log_event("ERROR", "DISCORD", f"Webhook delivery error | error: {e}")
        return False

def get_notification_logs(db: Session, limit: int = 50):
    """Retrieve logged system notifications from SQLite."""
    return db.query(NotificationDB).order_by(NotificationDB.id.desc()).limit(limit).all()
