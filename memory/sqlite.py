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
                name="",
                skills="",
                interests="",
                preferred_domains="",
                preferred_location="Remote",
                notification_preference="Discord"
            )
            db.add(default_user)
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
    
    # Dynamically update scores based on new profile
    recalculate_interest_scores(db, user)
    
    return user

def get_interest_scores(db: Session) -> List[InterestScoreDB]:
    return db.query(InterestScoreDB).all()

DOMAIN_RELATIONS = {
    "Artificial Intelligence": ["Machine Learning", "Data Science", "Natural Language Processing"],
    "Machine Learning": ["Artificial Intelligence", "Data Science", "Natural Language Processing"],
    "Data Science": ["Artificial Intelligence", "Machine Learning"],
    "Natural Language Processing": ["Artificial Intelligence", "Machine Learning"],
    "Full Stack Web Development": ["Frontend Development", "Backend Development"],
    "Frontend Development": ["Full Stack Web Development", "UI/UX Design"],
    "Backend Development": ["Full Stack Web Development", "Cloud Computing", "DevOps & SRE"],
    "Mobile App Development": ["Frontend Development", "UI/UX Design"],
    "DevOps & SRE": ["Cloud Computing", "Backend Development"],
    "Cloud Computing": ["DevOps & SRE", "Backend Development"],
    "Cybersecurity": ["Cloud Computing", "Backend Development"],
    "Game Development": ["UI/UX Design"],
    "Embedded Systems & IoT": ["Backend Development"],
    "Blockchain & Web3": ["Backend Development", "Cybersecurity"],
    "UI/UX Design": ["Frontend Development", "Mobile App Development"]
}

ALL_DOMAINS = list(DOMAIN_RELATIONS.keys())

def recalculate_interest_scores(db: Session, profile: UserDB):
    """Dynamically assign interest scores based on preferred_domains and skills."""
    
    # 1. Clear existing scores
    db.query(InterestScoreDB).delete()
    
    # 2. Extract keywords/domains from user profile
    selected_domains = [d.strip() for d in profile.preferred_domains.split(",") if d.strip()]
    
    # Simple check for keywords in skills/interests as fallback/boost
    profile_text = (profile.skills + " " + profile.interests).lower()
    
    for domain in ALL_DOMAINS:
        score = 10.0 # Base score for unselected domains
        
        # Check if domain was explicitly selected
        if domain in selected_domains:
            score = 90.0
        # Check if domain appears in skills/interests text
        elif domain.lower() in profile_text:
            score = 80.0
        # Check if it's a related domain
        else:
            for sel in selected_domains:
                if sel in DOMAIN_RELATIONS and domain in DOMAIN_RELATIONS[sel]:
                    score = max(score, 75.0) # Boost related domains
                    
        new_score = InterestScoreDB(topic=domain, score=score)
        db.add(new_score)
        
    db.commit()


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
