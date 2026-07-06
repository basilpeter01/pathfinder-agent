import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from models.schemas import Base, UserDB, InterestScoreDB, OpportunityDB, RoadmapDB, NotificationDB, ProfileSchema, OpportunitySchema
from typing import List, Optional
from datetime import datetime

# Initialize Database Engine
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "pathfinder.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Create all database tables and seed default user profile if empty."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user = db.query(UserDB).first()
        if not user:
            default_user = UserDB(
                name="User",
                skills="General Computing, Problem Solving, Software Basics",
                interests="Technology, Software Engineering, Innovation",
                preferred_domains="General Software, Tech Solutions",
                preferred_location="Remote / Flexible",
                notification_preference="Discord"
            )
            db.add(default_user)
            
            # Seed default interest scores
            default_scores = [
                InterestScoreDB(topic="Software Development", score=80.0),
                InterestScoreDB(topic="Technology", score=85.0),
                InterestScoreDB(topic="Web Development", score=75.0),
                InterestScoreDB(topic="Innovation", score=70.0)
            ]
            db.add_all(default_scores)
            db.commit()
        elif user.name == "Alex River":
            # Automatically migrate legacy Alex River demo database to generic Hello User
            user.name = "Hello User"
            user.skills = "General Computing, Problem Solving, Software Basics"
            user.interests = "Technology, Software Engineering, Innovation"
            user.preferred_domains = "General Software, Tech Solutions"
            user.preferred_location = "Remote / Flexible"
            db.query(InterestScoreDB).delete()
            default_scores = [
                InterestScoreDB(topic="Software Development", score=80.0),
                InterestScoreDB(topic="Technology", score=85.0),
                InterestScoreDB(topic="Web Development", score=75.0),
                InterestScoreDB(topic="Innovation", score=70.0)
            ]
            db.add_all(default_scores)
            db.commit()
    finally:
        db.close()

def get_db():
    """FastAPI dependency yielding db session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================
# CRUD Operations — Profile & Interests
# ==========================================

def get_user_profile(db: Session) -> UserDB:
    user = db.query(UserDB).first()
    if not user:
        init_db()
        user = db.query(UserDB).first()
    return user

def update_user_profile(db: Session, profile_data: ProfileSchema) -> UserDB:
    user = get_user_profile(db)
    user.name = profile_data.name
    user.skills = profile_data.skills
    user.interests = profile_data.interests
    user.preferred_domains = profile_data.preferred_domains
    user.preferred_location = profile_data.preferred_location
    user.notification_preference = profile_data.notification_preference
    db.commit()
    db.refresh(user)
    return user

def get_interest_scores(db: Session) -> List[InterestScoreDB]:
    return db.query(InterestScoreDB).all()

# ==========================================
# CRUD Operations — Opportunities
# ==========================================

def save_opportunities_to_db(db: Session, opportunities: List[OpportunitySchema]) -> List[OpportunityDB]:
    saved_list = []
    for opp in opportunities:
        existing = db.query(OpportunityDB).filter(OpportunityDB.url == opp.url).first()
        if existing:
            existing.score = opp.score
            existing.reason = opp.reason
            existing.source = opp.source
            saved_list.append(existing)
        else:
            new_opp = OpportunityDB(
                title=opp.title,
                company=opp.company,
                url=opp.url,
                source=opp.source,
                deadline=opp.deadline,
                score=opp.score,
                reason=opp.reason,
                is_notified=opp.is_notified
            )
            db.add(new_opp)
            saved_list.append(new_opp)
    db.commit()
    for s in saved_list:
        db.refresh(s)
    return saved_list

def get_stored_opportunities(db: Session, limit: int = 50) -> List[OpportunityDB]:
    return db.query(OpportunityDB).order_by(OpportunityDB.score.desc()).limit(limit).all()

# ==========================================
# CRUD Operations — Roadmaps
# ==========================================

def save_roadmap(db: Session, topic: str, content: str) -> RoadmapDB:
    existing = db.query(RoadmapDB).filter(RoadmapDB.topic == topic).first()
    if existing:
        existing.content = content
        db.commit()
        db.refresh(existing)
        return existing
    new_roadmap = RoadmapDB(topic=topic, content=content)
    db.add(new_roadmap)
    db.commit()
    db.refresh(new_roadmap)
    return new_roadmap

def get_roadmaps(db: Session) -> List[RoadmapDB]:
    return db.query(RoadmapDB).all()
