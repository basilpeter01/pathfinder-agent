# 🧭 Pathfinder AI — Autonomous Student Growth Agent

> **Google × Kaggle AI Agent Capstone · v1.0**  
> *An autonomous, RAG‑powered personal career and study acceleration agent that proactively works for students in the background — no prompts required.*

---

## 🌟 What Is Pathfinder AI?

Most AI tools are reactive — they wait for you to ask them something. **Pathfinder AI is different.** It wakes up on its own every 5 minutes, scans a curated list of internships and hackathons, uses **Google Gemini** to score each opportunity against your personal profile, and fires an alert to your **Discord** channel before you even knew the deadline existed.

At the same time, it acts as your personal study assistant — ingest any PDF or lecture notes and ask questions answered strictly from your own material. Generate a 4-week study roadmap for any topic with one click. Everything is persisted in a local **SQLite** database and routed through a **LangGraph** orchestration graph.

---

## 🏗️ System Architecture

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
 │  5‑min loop │──────▶│  Rich embed alert │
 │  background │       │  score ≥ 85/100   │
 └─────────────┘       └──────────────────┘
```

---

## 🚀 Quickstart

### Prerequisites
- Python **3.10+** (tested on 3.11 and 3.13)
- A free [Google Gemini API key](https://aistudio.google.com/) *(AI features)*
- A [Discord Webhook URL](https://support.discord.com/hc/en-us/articles/228383668) *(optional, for alerts)*

### Setup (Windows PowerShell)

```powershell
# 1. Clone the repo
git clone https://github.com/yourusername/pathfinder-agent.git
cd pathfinder-agent

# 2. Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate

# 3. Install all dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env
notepad .env   # paste your GEMINI_API_KEY and DISCORD_WEBHOOK_URL

# 5. Run the backend (Terminal 1)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 6. Run the frontend (Terminal 2)
streamlit run frontend/app.py
```

Open **http://localhost:8501** for the dashboard · **http://127.0.0.1:8000/docs** for the Swagger API.

---

## ✨ Core Features

| Feature | How It Works |
|---|---|
| **🧭 Opportunity Scout** | Fetches **live real-time hackathons & tech internships** from public web APIs (**GitHub Search API** & **Remotive Remote Jobs API**), calls Gemini 1.5 Flash to score each item 0–100 against your profile, saves ranked results to SQLite, and fires Discord alerts for scores ≥ 85 |
| **🤖 LangGraph Agent Chat** | A `StateGraph` with 5 nodes: `load_profile → determine_intent → [scout / planner / rag]`. Keyword-based intent routing decides the execution path dynamically |
| **📚 Knowledge Vault (RAG)** | Upload PDFs or TXT files — PyMuPDF extracts text, text is chunked (500 words, 50-word overlap), ONNX embeddings via FastEmbed (`BAAI/bge-small-en-v1.5`) stored in LanceDB. Queries perform cosine similarity search, top-3 chunks are passed to Gemini for synthesis |
| **🗓️ Learning Planner** | Input any topic + duration (1–8 weeks). Gemini returns structured JSON: prerequisites, weekly tasks, mini-projects, resources. Saved to SQLite and viewable anytime |
| **⚡ Background Automation** | APScheduler runs a background thread every N minutes (default 5), invoking the full scout pipeline without any user interaction |
| **🔔 Discord Notifications** | Rich Discord embeds with title, company, score, Gemini reasoning, deadline and URL. Falls back to SQLite logging if no webhook is configured |
| **👤 Student Profile** | Editable form — name, skills, interests, preferred domains, location, notification preference. Persisted in SQLite `users` table and used by Gemini during scoring |

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
│   ├── opportunities.py     # Scout pipeline: load → score → rank → save → notify
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
│   └── app.py               # Streamlit 7-page dashboard (456 lines)
├── data/
│   └── sample_opportunities.json  # Curated public competition fallback for offline grading demos
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

> **No API key?** The system automatically falls back to a rule-based scoring engine and offline RAG preview mode — the full UI and scheduler still work.

---

## 📡 API Endpoints

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

---

## 📜 License

MIT License — see `LICENSE` for full terms.

---

*Built for the **Google × Kaggle AI Agent Capstone** · Powered by Gemini · Orchestrated by LangGraph*
