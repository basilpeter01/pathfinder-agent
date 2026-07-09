import os
import shutil
import json
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Dict
from contextlib import asynccontextmanager

from memory.sqlite import get_db, init_db, get_user_profile, update_user_profile, get_stored_opportunities, save_roadmap, get_roadmaps
from models.schemas import ProfileSchema, QuestionRequest, QuestionResponse, RoadmapRequest, RoadmapResponse
from services.opportunities import run_opportunity_scout_pipeline
from memory.lancedb import query_vault, list_vault_documents
from rag.ingest import process_and_ingest_file, UPLOADS_DIR
from services.gemini import answer_question_with_rag, generate_learning_roadmap
from agent.graph import run_agent_workflow
from scheduler.jobs import start_scheduler, stop_scheduler, get_scheduler_status, scheduled_scout_job, manual_scout_job
from services.discord import get_notification_logs

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure SQLite tables are seeded and background scheduler is started/stopped."""
    init_db()
    start_scheduler()
    yield
    stop_scheduler()

app = FastAPI(
    title="Pathfinder AI API",
    description="Backend for Pathfinder AI - Autonomous Student Growth Agent (Complete Capstone v1)",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "working", "service": "Pathfinder AI Backend v1"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

# ==========================================
# Profile Endpoints (Phase 3)
# ==========================================

@app.get("/profile", response_model=ProfileSchema)
def get_profile(db: Session = Depends(get_db)):
    return get_user_profile(db)

@app.post("/profile", response_model=ProfileSchema)
def update_profile(profile: ProfileSchema, db: Session = Depends(get_db)):
    return update_user_profile(db, profile)

# ==========================================
# Opportunity Scout Endpoints (Phase 4 & 5)
# ==========================================

@app.get("/opportunities")
def list_opportunities(db: Session = Depends(get_db)):
    """Return stored opportunities. Does NOT auto-trigger the scout pipeline to avoid timeouts."""
    opps = get_stored_opportunities(db)
    return opps

@app.post("/run-agent")
def trigger_opportunity_scout(db: Session = Depends(get_db)):
    """Manually trigger the Opportunity Scout pipeline."""
    scored_opps = run_opportunity_scout_pipeline(db)
    return {
        "status": "success",
        "message": f"Scout pipeline ran successfully. Evaluated and ranked {len(scored_opps)} opportunities.",
        "opportunities_count": len(scored_opps)
    }

# ==========================================
# RAG Knowledge Vault Endpoints (Phase 6)
# ==========================================

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload PDF or TXT file to Knowledge Vault and ingest into LanceDB."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename missing")
        
    safe_filename = os.path.basename(file.filename)
    file_path = os.path.join(UPLOADS_DIR, safe_filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        chunks_count = process_and_ingest_file(file_path, safe_filename)
        return {
            "status": "success",
            "filename": safe_filename,
            "chunks_ingested": chunks_count,
            "message": f"Successfully ingested {chunks_count} chunks into Knowledge Vault."
        }
    except Exception as e:
        print(f"[Upload Error] {e}")
        raise HTTPException(status_code=500, detail="Failed to process uploaded file. Please check server logs.")

@app.get("/vault/documents")
def get_vault_docs():
    """List all documents currently ingested in LanceDB Knowledge Vault."""
    docs = list_vault_documents()
    return {"documents": docs, "count": len(docs)}

@app.post("/ask", response_model=QuestionResponse)
def ask_question(request: QuestionRequest):
    """Retrieve relevant chunks from LanceDB and answer via Gemini LLM."""
    retrieved = query_vault(request.question, n_results=3)
    chunks = [r["text"] for r in retrieved]
    sources = list(set([r["source"] for r in retrieved]))
    
    answer = answer_question_with_rag(request.question, chunks)
    return QuestionResponse(answer=answer, sources=sources)

# ==========================================
# Learning Planner Endpoints (Phase 7)
# ==========================================

@app.post("/roadmap", response_model=RoadmapResponse)
def create_roadmap(request: RoadmapRequest, db: Session = Depends(get_db)):
    """Generate and store a structured study roadmap."""
    roadmap_data = generate_learning_roadmap(request.topic, request.duration_weeks)
    save_roadmap(db, request.topic, json.dumps(roadmap_data, indent=2))
    return RoadmapResponse(**roadmap_data)

@app.get("/roadmaps")
def list_roadmaps(db: Session = Depends(get_db)):
    """List all saved learning roadmaps from SQLite."""
    roadmaps = get_roadmaps(db)
    return [{"id": r.id, "topic": r.topic, "content": r.content} for r in roadmaps]

# ==========================================
# LangGraph Orchestration Endpoint (Phase 8)
# ==========================================

@app.post("/agent/chat")
def agent_chat(payload: Dict[str, str] = Body(...)):
    """Invoke LangGraph agent to classify intent and execute Scout, Planner, or RAG."""
    user_input = payload.get("user_input", "")
    if not user_input:
        raise HTTPException(status_code=400, detail="user_input required")
    return run_agent_workflow(user_input)

# ==========================================
# Scheduler & Notification Endpoints (Phase 9 & 10)
# ==========================================

@app.get("/scheduler/status")
def scheduler_status():
    """Get status of background APScheduler loop."""
    return get_scheduler_status()

@app.post("/scheduler/trigger")
def trigger_scheduler_job():
    """Manually trigger scout with Gemini LLM scoring (for user-initiated runs)."""
    manual_scout_job()
    return {"status": "success", "message": "Scouting pass executed successfully."}

@app.get("/notifications")
def list_notifications(db: Session = Depends(get_db)):
    """Retrieve logged system notifications and Discord alert history."""
    notifs = get_notification_logs(db, limit=50)
    return [{"id": n.id, "title": n.title, "message": n.message, "url": n.url, "timestamp": n.timestamp} for n in notifs]
