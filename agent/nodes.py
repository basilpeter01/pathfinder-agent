from typing import Dict, Any, TypedDict, Optional
from sqlalchemy.orm import Session
from memory.sqlite import SessionLocal, get_user_profile, save_roadmap
from services.opportunities import run_opportunity_scout_pipeline
from services.gemini import answer_question_with_rag, generate_learning_roadmap
from memory.lancedb import query_vault

class AgentState(TypedDict):
    user_input: str
    profile_loaded: bool
    intent: str
    response: str
    metadata: Dict[str, Any]

def load_profile_node(state: AgentState) -> AgentState:
    """Load user profile from SQLite DB."""
    db = SessionLocal()
    try:
        user = get_user_profile(db)
        state["profile_loaded"] = True
        state["metadata"]["user_name"] = user.name
        state["metadata"]["skills"] = user.skills
        state["metadata"]["domains"] = user.preferred_domains
    except Exception as e:
        state["profile_loaded"] = False
        state["metadata"]["error"] = str(e)
    finally:
        db.close()
    return state

def determine_intent_node(state: AgentState) -> AgentState:
    """Classify user input into one of three core workflows: opportunity, learning, or question."""
    text = state["user_input"].lower()
    
    if any(k in text for k in ["scout", "opportunity", "internship", "hackathon", "job", "career", "rank", "find me"]):
        state["intent"] = "opportunity"
    elif any(k in text for k in ["learn", "roadmap", "study plan", "how to", "master", "guide", "syllabus", "teach me"]):
        state["intent"] = "learning"
    else:
        # Default to RAG study question answering
        state["intent"] = "question"
    return state

def scout_node(state: AgentState) -> AgentState:
    """Execute autonomous opportunity scout pipeline."""
    db = SessionLocal()
    try:
        opps = run_opportunity_scout_pipeline(db)
        top_title = opps[0].title if opps else "No opportunities found"
        state["response"] = f"⚡ Autonomous Scout Completed! Evaluated and ranked {len(opps)} opportunities against your profile. Top match: **{top_title}**."
        state["metadata"]["opportunities_count"] = len(opps)
    except Exception as e:
        state["response"] = f"Scout error: {e}"
    finally:
        db.close()
    return state

def planner_node(state: AgentState) -> AgentState:
    """Generate and store learning roadmap."""
    topic = state["user_input"].replace("learn", "").replace("roadmap for", "").replace("how to", "").strip()
    if not topic:
        topic = "FastAPI & AI Agents"
        
    db = SessionLocal()
    try:
        roadmap = generate_learning_roadmap(topic, weeks=4)
        save_roadmap(db, topic, str(roadmap))
        state["response"] = f"🎯 Created a custom 4-week study roadmap for **{topic}**! Check the Learning Planner tab to view timeline, prerequisites, and mini-capstone projects."
        state["metadata"]["roadmap_topic"] = topic
    except Exception as e:
        state["response"] = f"Planner error: {e}"
    finally:
        db.close()
    return state

def rag_node(state: AgentState) -> AgentState:
    """Retrieve chunks from ChromaDB Knowledge Vault and answer via Gemini."""
    query = state["user_input"]
    retrieved = query_vault(query, n_results=3)
    chunks = [r["text"] for r in retrieved]
    sources = list(set([r["source"] for r in retrieved]))
    
    ans = answer_question_with_rag(query, chunks)
    state["response"] = ans
    state["metadata"]["sources"] = sources
    return state
