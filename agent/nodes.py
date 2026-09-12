import re
import json
from typing import Dict, Any, TypedDict, Optional
from sqlalchemy.orm import Session
from memory.sqlite import SessionLocal, get_user_profile, save_roadmap
from services.opportunities import run_opportunity_scout_pipeline
from services.gemini import answer_question_with_rag, generate_learning_roadmap
from memory.lancedb import query_vault
from services.logger import log_event

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
        log_event("INFO", "AGENT", f"Node: 'load_profile' -> Loaded profile for '{user.name}'")
    except Exception as e:
        state["profile_loaded"] = False
        state["metadata"]["error"] = str(e)
        log_event("ERROR", "AGENT", f"Node: 'load_profile' failed | error: {e}")
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
    log_event("INFO", "AGENT", f"Node: 'determine_intent' -> Routed to '{state['intent']}' workflow")
    return state

def scout_node(state: AgentState) -> AgentState:
    """Execute autonomous opportunity scout pipeline."""
    log_event("INFO", "AGENT", "Node: 'scout' -> Executing opportunity scout workflow")
    db = SessionLocal()
    try:
        opps = run_opportunity_scout_pipeline(db, use_llm=True)
        top_title = opps[0].title if opps else "No opportunities found"
        state["response"] = f"Autonomous Scout Completed! Evaluated and ranked {len(opps)} opportunities against your profile. Top match: **{top_title}**."
        state["metadata"]["opportunities_count"] = len(opps)
        log_event("INFO", "AGENT", f"Node: 'scout' -> Completed. Evaluated {len(opps)} items")
    except Exception as e:
        state["response"] = f"Scout error: {e}"
        log_event("ERROR", "AGENT", f"Node: 'scout' failed | error: {e}")
    finally:
        db.close()
    return state

def planner_node(state: AgentState) -> AgentState:
    """Generate and store learning roadmap."""
    text = state["user_input"]
    for phrase in [
        "create a study roadmap for", "create study roadmap for", "create a roadmap for", "create roadmap for",
        "study roadmap for", "roadmap for", "how to learn", "how to master", "teach me how to", "teach me",
        "learn about", "learn", "study plan for", "study plan", "guide for", "guide on",
        "give me a roadmap for", "give me a roadmap to learn", "create a study"
    ]:
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        text = pattern.sub("", text)
    topic = " ".join(text.split()).strip(" :-.")
    if not topic or len(topic) < 2:
        topic = state["user_input"].strip()
        
    log_event("INFO", "AGENT", f"Node: 'planner' -> Generating roadmap for: '{topic}'")
    db = SessionLocal()
    try:
        roadmap = generate_learning_roadmap(topic, weeks=4)
        save_roadmap(db, topic, json.dumps(roadmap, indent=2))
        log_event("INFO", "AGENT", f"Node: 'planner' -> Roadmap generated and saved for '{topic}'")
        
        prereqs = ", ".join([f"`{p}`" for p in roadmap.get("prerequisites", [])])
        weeks_md = ""
        for w in roadmap.get("weekly_roadmap", []):
            week_num = w.get("week", "")
            focus = w.get("focus", "")
            tasks = "\n".join([f"  - {t}" for t in w.get("tasks", [])])
            weeks_md += f"\n**Week {week_num}: {focus}**\n{tasks}\n"
            
        projects = ", ".join([f"**{p}**" for p in roadmap.get("mini_projects", [])])
        resources = ", ".join([f"`{r}`" for r in roadmap.get("resources", [])])
        
        state["response"] = (
            f"**Created a custom 4-week study roadmap for [{topic}]!**\n\n"
            f"**Prerequisites:** {prereqs}\n"
            f"{weeks_md}\n"
            f"**Mini-Projects:** {projects}\n"
            f"**Recommended Resources:** {resources}\n\n"
            f"*Tip: This roadmap has been saved. You can review or track it anytime under the **Learning Planner** tab.*"
        )
        state["metadata"]["roadmap_topic"] = topic
    except Exception as e:
        state["response"] = f"Planner error: {e}"
        log_event("ERROR", "AGENT", f"Node: 'planner' failed | error: {e}")
    finally:
        db.close()
    return state

def rag_node(state: AgentState) -> AgentState:
    """Retrieve chunks from LanceDB Knowledge Vault and answer via Gemini."""
    query = state["user_input"]
    log_event("INFO", "AGENT", f"Node: 'rag' -> Searching Knowledge Vault for: \"{query[:40]}...\"")
    retrieved = query_vault(query, n_results=3)
    chunks = [r["text"] for r in retrieved]
    sources = list(set([r["source"] for r in retrieved]))
    log_event("INFO", "AGENT", f"Node: 'rag' -> Retrieved {len(chunks)} context chunks from {len(sources)} sources")
    
    ans = answer_question_with_rag(query, chunks)
    state["response"] = ans
    state["metadata"]["sources"] = sources
    log_event("INFO", "AGENT", f"Node: 'rag' -> Completed answer generation")
    return state
