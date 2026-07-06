from sqlalchemy import Column, Integer, String, Float, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

Base = declarative_base()

# ==========================================
# SQLAlchemy Database Models (SQLite)
# ==========================================

class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, default="Student")
    skills = Column(String, default="Python, Data Science") # Comma-separated
    interests = Column(String, default="AI, Machine Learning, Hackathons") # Comma-separated
    preferred_domains = Column(String, default="Artificial Intelligence, Backend")
    preferred_location = Column(String, default="Remote")
    notification_preference = Column(String, default="Discord")

class InterestScoreDB(Base):
    __tablename__ = "interest_scores"
    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String, unique=True, index=True)
    score = Column(Float, default=50.0) # 0 to 100

class OpportunityDB(Base):
    __tablename__ = "opportunities"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    company = Column(String)
    url = Column(String)
    source = Column(String, default="Scout")
    deadline = Column(String)
    score = Column(Float, default=0.0)
    reason = Column(Text, default="")
    is_notified = Column(Boolean, default=False)

class RoadmapDB(Base):
    __tablename__ = "roadmaps"
    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String, index=True)
    content = Column(Text)

class NotificationDB(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    message = Column(Text)
    url = Column(String, nullable=True)
    timestamp = Column(String)

# ==========================================
# Pydantic Schemas (API Requests/Responses)
# ==========================================

class ProfileSchema(BaseModel):
    name: str = "Student"
    skills: str = "Python, Data Science"
    interests: str = "AI, Machine Learning, Hackathons"
    preferred_domains: str = "Artificial Intelligence, Backend"
    preferred_location: str = "Remote"
    notification_preference: str = "Discord"

    class Config:
        from_attributes = True

class InterestScoreSchema(BaseModel):
    topic: str
    score: float

class OpportunitySchema(BaseModel):
    id: Optional[int] = None
    title: str
    company: str
    url: str
    source: str = "Scout"
    deadline: str
    score: float = 0.0
    reason: str = ""
    is_notified: bool = False

    class Config:
        from_attributes = True

class QuestionRequest(BaseModel):
    question: str

class QuestionResponse(BaseModel):
    answer: str
    sources: List[str] = []

class RoadmapRequest(BaseModel):
    topic: str
    duration_weeks: int = 4

class RoadmapResponse(BaseModel):
    topic: str
    prerequisites: List[str]
    weekly_roadmap: List[Dict[str, Any]]
    mini_projects: List[str]
    resources: List[str]
