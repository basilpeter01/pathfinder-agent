# 🧭 Pathfinder AI — Autonomous Student Growth Agent

> **Google × Kaggle AI Agent Capstone · v1.0**
> *An autonomous, RAG-powered career and study acceleration agent that proactively scouts opportunities, answers questions from your own notes, and builds personalised learning roadmaps — all without waiting to be asked.*

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python) ![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-orange) ![Gemini](https://img.shields.io/badge/LLM-Gemini%201.5%20Flash-brightgreen?logo=google) ![License](https://img.shields.io/badge/License-MIT-lightgrey)

---

## 🎯 The Problem

Students juggle hundreds of applications, study deadlines, and skill gaps simultaneously — yet every existing AI tool sits idle until the student asks a question. Pathfinder AI flips this model: it runs in the background, autonomously scans live internship boards and hackathon listings, scores each opportunity against your personal profile using Gemini, and fires a Discord alert before you even knew the deadline existed.

---

## 🚀 The Solution

Pathfinder AI is a **fully autonomous, multi-workflow AI agent** that combines:

- **Proactive Opportunity Scouting** — Pulls live data from GitHub and Remotive APIs, then uses Gemini 1.5 Flash to score opportunities 0–100 against your skill set and preferred domains. High-scoring matches (≥ 85) trigger a rich Discord embed in real time.
- **Conversational RAG Assistant** — Upload any PDF or lecture notes; the agent chunks, embeds (BAAI/bge-small-en-v1.5 via FastEmbed ONNX), stores in LanceDB, and answers questions grounded *strictly* in your own material.
- **AI Learning Planner** — Ask for a roadmap and Gemini returns a structured 4-week plan with prerequisites, weekly tasks, mini-projects, and curated resources — saved and browsable forever.
- **Background Automation** — APScheduler runs the full scout pipeline every N minutes (default: 5) in a background thread with zero user interaction.

---

## 🏗️ Architecture

```text
╔══════════════════════════════════════════════════════════════╗
║            Streamlit Dashboard  (Port 8501)                  ║
║   Dashboard · Agent Chat · Scout · RAG · Planner · Profile   ║
╚══════════════════╦═══════════════════════════════════════════╝
                   ║  HTTP REST (requests library)
                   ▼
╔══════════════════════════════════════════════════════════════╗
║             FastAPI Backend  (Port 8000)                     ║
║  /profile · /opportunities · /upload · /ask · /roadmap       ║
║  /run-agent · /agent/chat · /scheduler/* · /notifications    ║
╚═══════╦═══════════════╦════════════════╦═════════════════════╝
        ║               ║                ║
        ▼               ▼                ▼
 ┌─────────────┐  ┌──────────┐   ┌─────────────────┐
 │  LangGraph  │  │  SQLite  │   │  LanceDB         │
 │  StateGraph │  │  Memory  │   │  Vector Store    │
 │             │  │          │   │  (FastEmbed ONNX)│
 │ load_profile│  │ users    │   └────────┬────────┘
 │ intent_node │  │ opportun.│            │
 │ scout_node  │  │ roadmaps │   ┌────────▼────────┐
 │ planner_node│  │ notifs   │   │  RAG Ingest     │
 │ rag_node    │  │ interest │   │  PyMuPDF →      │
 └──────┬──────┘  └──────────┘   │  Chunk → Embed  │
        ║                        └─────────────────┘
        ▼
╔══════════════════════════════════════════════════════════════╗
║              Google Gemini 1.5 Flash (LLM)                   ║
║   Opportunity Scoring · RAG Answer Synthesis · Roadmaps       ║
╚═══════════════════╦══════════════════════════════════════════╝
                    ║
        ┌───────────┴──────────┐
        ▼                      ▼
 ┌─────────────┐       ┌──────────────────┐
 │  APScheduler│       │  Discord Webhook  │
 │  5-min loop │──────▶│  Rich embed alert │
 │  background │       │  score ≥ 85/100   │
 └─────────────┘       └──────────────────┘
```

### LangGraph Workflow — Node by Node

The orchestration graph (`agent/graph.py`) is a **compiled `StateGraph`** that passes a single `AgentState` TypedDict through five nodes:

| Step | Node | Responsibility |
|------|------|----------------|
| 1 | `load_profile_node` | Reads the student profile (name, skills, domains) from SQLite into shared state |
| 2 | `determine_intent_node` | Keyword-based classifier; routes to `opportunity`, `learning`, or `question` |
| 3a | `scout_node` | Fetches live APIs → Gemini scores each opportunity → saves to SQLite → Discord alert |
| 3b | `planner_node` | Extracts topic from input → Gemini generates structured JSON roadmap → saves to SQLite |
| 3c | `rag_node` | LanceDB cosine-similarity search (top-3 chunks) → Gemini synthesises grounded answer |

> The graph includes a **sequential fallback runner** — if `langgraph` is unavailable, nodes execute in the same logical order without the compiled graph.

---

## 🛠️ Setup Instructions

### Prerequisites

- **Python 3.10+** (tested on 3.11 and 3.13)
- A free [Google Gemini API key](https://aistudio.google.com/) — required for LLM features
- A [Discord Webhook URL](https://support.discord.com/hc/en-us/articles/228383668) — *optional*, for real-time alerts

### Installation

```powershell
# 1. Clone the repository
git clone https://github.com/basilpeter01/kaggle-capstone-project.git
cd kaggle-capstone-project

# 2. Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\activate          # Windows
# source venv/bin/activate       # macOS / Linux

# 3. Install all pinned dependencies
pip install -r requirements.txt

# 4. Configure environment variables
copy .env.example .env
notepad .env   # Set GEMINI_API_KEY and (optionally) DISCORD_WEBHOOK_URL
```

### Running Locally

Open **two terminals** in the project root:

```powershell
# Terminal 1 — FastAPI backend
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — Streamlit frontend
streamlit run frontend/app.py
```

| Service | URL |
|---------|-----|
| **Streamlit Dashboard** | http://localhost:8501 |
| **FastAPI Swagger Docs** | http://127.0.0.1:8000/docs |

> **No API key?** The system automatically falls back to a rule-based scoring engine and offline RAG preview mode — the full UI and scheduler still run.

---

## 💬 Usage

### 1. Fill in Your Profile
Navigate to the **Profile** tab and enter your name, skills, interests, and preferred domains. This profile is used by Gemini every time it scores an opportunity.

### 2. Chat with the Agent

Open the **Agent Chat** tab and type naturally. Example prompts:

| Intent | Example |
|--------|---------|
| Opportunity Scout | `"Find me AI internships"` |
| Learning Planner | `"Give me a roadmap to learn FastAPI"` |
| RAG Q&A | `"What is gradient descent?"` (after uploading notes) |

The agent classifies your intent, routes through the LangGraph graph, and returns a grounded response.

### 3. Upload Study Material
Go to **Knowledge Vault** → Upload a PDF or TXT file. The system extracts text, chunks it (500 words, 50-word overlap), embeds it with BAAI/bge-small-en-v1.5, and stores it in LanceDB — ready for RAG queries instantly.

### 4. Automated Scouting
The background scheduler starts automatically on server boot. Every 5 minutes (configurable via `SCOUT_INTERVAL_MINUTES`) it runs the full scout pipeline and pushes Discord alerts for any opportunity scoring ≥ 85. You can also trigger it manually from the **Scout** tab.

### 5. Learning Roadmaps
Go to **Learning Planner**, enter a topic and duration (1–8 weeks). Gemini returns a structured plan (prerequisites, weekly tasks, mini-projects, resources) saved to SQLite and viewable in the Roadmaps panel.

---

## 🧠 Methodology & Design Choices

This section documents the **why** behind each major architectural decision.

### Why LangGraph instead of a plain chain?

Most basic LLM apps use a simple sequential chain — every input goes through the same steps. Pathfinder AI has **three fundamentally different execution paths** (scout, plan, answer). LangGraph's `StateGraph` lets us express this as a compiled, inspectable directed graph with conditional edges, making the routing logic explicit and auditable rather than buried in `if/else` blocks scattered across services.

The `AgentState` TypedDict is a single shared context dictionary that every node reads from and writes to — this mirrors the standard agentic pattern where agents accumulate context as they progress through a workflow.

### Why LanceDB + FastEmbed (ONNX) for vectors?

LanceDB is embedded (no separate server process), columnar (built on Apache Arrow/Lance format), and ships a Python-native API — ideal for a capstone project that needs to be reproducible on any machine without Docker. FastEmbed's ONNX runtime for `BAAI/bge-small-en-v1.5` means embeddings run locally with no API calls, keeping the RAG pipeline fully offline-capable and cost-free.

### Why keyword-based intent classification instead of an LLM router?

Using Gemini to classify intent would add latency and token cost on *every* message before the actual task even begins. A lightweight keyword matcher (`determine_intent_node`) covers the three clearly-delineated intent classes with near-zero overhead and is completely transparent — you can read the exact trigger words in `agent/nodes.py`. For a student-facing tool where the three modes are well-understood by the user, this is a deliberate pragmatic trade-off.

### Why APScheduler + background thread instead of a cron job or Celery?

The project must run with a single `uvicorn` command — no Redis, no worker processes, no system cron. APScheduler's `BackgroundScheduler` attaches directly to the FastAPI process lifecycle (started in `startup`, shut down in `shutdown`) and runs the scout pipeline in a daemon thread. This keeps the setup to a two-terminal workflow (backend + frontend) that any student can reproduce.

### Why SQLite + SQLAlchemy for relational data?

Profiles, opportunities, roadmaps, and notification logs are all relational by nature (foreign keys, ordering, filtering). SQLite is zero-config, file-based, and ships with Python — appropriate for a local-first capstone project. SQLAlchemy's ORM gives type-safe model definitions and easy migration to PostgreSQL if the project scales up.

### Graceful Degradation Strategy

Every external dependency (Gemini API, Discord webhook, live web APIs) has a fallback:

- **No Gemini key** → Rule-based opportunity scoring + offline RAG preview mode
- **Live APIs down** → Falls back to `data/sample_opportunities.json` curated dataset
- **No Discord webhook** → Notifications are logged to SQLite instead
- **LangGraph import failure** → Sequential fallback runner executes nodes in order

This ensures the full UI and scheduler remain functional during judging even without API access.

---

## ✨ Core Features

| Feature | How It Works |
|---|---|
| **🧭 Opportunity Scout** | Fetches **live** hackathons & internships from GitHub Search API and Remotive Remote Jobs API, calls Gemini 1.5 Flash to score each 0–100 against your profile, saves ranked results to SQLite, and fires Discord alerts for scores ≥ 85 |
| **🤖 LangGraph Agent Chat** | A compiled `StateGraph` with 5 nodes: `load_profile → determine_intent → [scout / planner / rag]`. Keyword-based intent routing decides the execution path dynamically |
| **📚 Knowledge Vault (RAG)** | Upload PDFs or TXT files — PyMuPDF extracts text, chunked (500 words, 50-word overlap), ONNX embeddings via FastEmbed stored in LanceDB. Cosine similarity search returns top-3 chunks for Gemini synthesis |
| **🗓️ Learning Planner** | Input any topic + duration (1–8 weeks). Gemini returns structured JSON: prerequisites, weekly tasks, mini-projects, resources. Saved to SQLite and viewable anytime |
| **⚡ Background Automation** | APScheduler runs a daemon thread every N minutes (default 5), invoking the full scout pipeline without any user interaction |
| **🔔 Discord Notifications** | Rich Discord embeds with title, company, score, Gemini reasoning, deadline and URL. Falls back to SQLite logging if no webhook is configured |
| **👤 Student Profile** | Editable form — name, skills, interests, preferred domains, location, notification preference. Persisted in SQLite and used by Gemini during scoring |

---

## 🛠️ Tech Stack

| Layer | Technology | Version |
|---|---|---|
| **UI** | Streamlit | 1.58.0 |
| **Backend API** | FastAPI + Uvicorn | 0.139.0 / 0.34.0 |
| **Agent Orchestration** | LangGraph (StateGraph) | 1.2.7 |
| **LLM** | Google Gemini 1.5 Flash (`google-genai`) | ≥ 1.16.0 |
| **Vector Store** | LanceDB + FastEmbed (ONNX) | ≥ 0.17.0 / ≥ 0.8.0 |
| **Relational DB** | SQLite via SQLAlchemy | 2.0.38 |
| **PDF Parsing** | PyMuPDF (fitz) | 1.28.0 |
| **Scheduler** | APScheduler (BackgroundScheduler) | 3.11.3 |
| **Notifications** | discord-webhook | 1.3.1 |
| **Data Validation** | Pydantic v2 | 2.10.6 |
| **Arrow / Columnar** | PyArrow | ≥ 15.0.0 |

---

## 📁 Project Structure

```text
pathfinder-agent/
├── backend/
│   └── main.py              # FastAPI app, all routes, startup/shutdown lifecycle
├── agent/
│   ├── graph.py             # LangGraph StateGraph builder + run_agent_workflow()
│   └── nodes.py             # AgentState TypedDict + 5 node functions
├── services/
│   ├── gemini.py            # Gemini API calls: scoring, RAG QA, roadmap generation
│   ├── opportunities.py     # Scout pipeline: fetch → score → rank → save → notify
│   └── discord.py           # Discord webhook sender + notification DB logger
├── memory/
│   ├── sqlite.py            # SQLAlchemy engine, CRUD for profile/opps/roadmaps
│   └── lancedb.py           # LanceDB connection, embedding, insert, similarity search
├── rag/
│   └── ingest.py            # PyMuPDF text extraction + chunking → LanceDB
├── scheduler/
│   └── jobs.py              # APScheduler setup, start/stop, status, cron job
├── models/
│   └── schemas.py           # SQLAlchemy ORM models + Pydantic request/response schemas
├── frontend/
│   └── app.py               # Streamlit 7-page dashboard
├── data/
│   └── sample_opportunities.json  # Curated fallback dataset for offline/demo mode
├── .env.example             # Environment variable template
├── requirements.txt         # All pinned Python dependencies
└── guide.md                 # Full developer handbook (architecture, internals, FAQ)
```

---

## 🔑 Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | ✅ Yes | Google Gemini API key from AI Studio |
| `DISCORD_WEBHOOK_URL` | Optional | Discord webhook for real-time alerts |
| `DATABASE_URL` | Auto | SQLite path (default: `sqlite:///./data/pathfinder.db`) |
| `UPLOADS_DIR` | Auto | Upload directory for PDFs (default: `./uploads`) |
| `SCOUT_INTERVAL_MINUTES` | Optional | Background loop interval (default: `5`) |
| `DISCORD_SCORE_THRESHOLD` | Optional | Minimum score to trigger Discord alert (default: `85`) |

---

## 📡 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET/POST` | `/profile` | Read / update student profile |
| `GET` | `/opportunities` | List ranked opportunities |
| `POST` | `/run-agent` | Manually trigger scout pipeline |
| `POST` | `/upload` | Upload PDF/TXT to Knowledge Vault |
| `GET` | `/vault/documents` | List ingested documents |
| `POST` | `/ask` | RAG query answered by Gemini |
| `POST` | `/roadmap` | Generate + save learning roadmap |
| `GET` | `/roadmaps` | List all saved roadmaps |
| `POST` | `/agent/chat` | LangGraph agent chat endpoint |
| `GET` | `/scheduler/status` | APScheduler status |
| `POST` | `/scheduler/trigger` | Trigger background job immediately |
| `GET` | `/notifications` | List SQLite notification logs |

Full interactive docs available at **http://127.0.0.1:8000/docs** (Swagger UI).

---

## 📜 License

MIT License — see `LICENSE` for full terms.

---

*Built for the **Google × Kaggle AI Agent Capstone** · Powered by Gemini · Orchestrated by LangGraph*
