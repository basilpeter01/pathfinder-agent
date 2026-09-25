# 🧭 Pathfinder

A full-stack project to keep track of internships, hackathons, study material, and learning plans in one place.

Instead of manually checking job boards every day, Pathfinder runs in the background, grabs live opportunities, scores them against user skills using Gemini, and pings Discord when a good match shows up. It also has a local RAG assistant to ask questions from uploaded files and a planner to generate study roadmaps.

---

## 🎯 What it Does

* **Automated Opportunity Scouting:** Pulls listings from the GitHub Search API and Remotive Jobs API every few minutes. It uses Google Gemini Flash to compare the job description with saved profile and gives it a match score from 0 to 100.
* **Discord Alerts:** If an opportunity scores 85 or higher, it sends a Discord notification via webhook. If no webhook is configured, it just saves them locally to SQLite.
* **Note Search & Q&A (RAG):** Upload class notes or textbooks. It extracts the text, chunks it, embeds it locally using `bge-small-en-v1.5` through FastEmbed (ONNX), and stores it in LanceDB. Ask questions and get answers from files without relying on external embedding APIs.
* **Study Roadmap Generator:** Enter any tech stack or topic along with a target duration (1–8 weeks), and Gemini outputs a weekly breakdown with topics, practice projects, and resources.
* **Background Scheduler:** Uses APScheduler to run the scout loop automatically every 5 minutes in a separate daemon thread while the FastAPI server is running.

---

## 🏗️ Architecture

```text
╔══════════════════════════════════════════════════════════════╗
║            Streamlit Frontend  (Port 8501)                   ║
║   Dashboard · Agent Chat · Scout · Vault · Planner · Profile ║
╚══════════════════╦═══════════════════════════════════════════╝
                   ║  REST API (requests)
                   ▼
╔══════════════════════════════════════════════════════════════╗
║             FastAPI Backend  (Port 8000)                     ║
║  Routes: /profile, /opportunities, /upload, /ask, /roadmap   ║
╚═══════╦═══════════════╦════════════════╦═════════════════════╝
        ║               ║                ║
        ▼               ▼                ▼
 ┌─────────────┐  ┌──────────┐   ┌─────────────────┐
 │  LangGraph  │  │  SQLite  │   │  LanceDB        │
 │  Workflow   │  │  Storage │   │  Vector DB      │
 │             │  │          │   │  (FastEmbed     │
 │ StateGraph  │  │ profiles │   │   local ONNX)   │
 │ routing &   │  │ jobs     │   └────────┬────────┘
 │ state mgmt  │  │ roadmaps │            │
 └──────┬──────┘  │ logs     │   ┌────────▼────────┐
        │         └──────────┘   │  PyMuPDF        │
        │                        │  Text Extraction│
        ▼                        └─────────────────┘
╔══════════════════════════════════════════════════════════════╗
║                Google Gemini (Flash API)                     ║
║   Scoring Jobs · Answering RAG Prompts · Making Roadmaps     ║
╚═══════════════════╦══════════════════════════════════════════╝
                    ║
        ┌───────────┴──────────┐
        ▼                      ▼
 ┌─────────────┐       ┌──────────────────┐
 │  APScheduler│       │  Discord Webhook │
 │ 5-min timer │──────▶│  Alert on score  │
 │ in backend  │       │  >= 85           │
 └─────────────┘       └──────────────────┘
```

---

## ⚙️ How the Workflow Runs (LangGraph)

The backend uses a LangGraph `StateGraph` with a shared dictionary (`AgentState`) to handle incoming requests step-by-step:

1. **`load_profile_node`**: Fetches the user's saved skills and domain preferences from SQLite.
2. **`determine_intent_node`**: Looks at the user input to route the request to the right handler:
   - Keywords like "internship", "job", "hackathon", "scout" → `scout_node`
   - Keywords like "roadmap", "learn", "study plan" → `planner_node`
   - General questions about uploaded material → `rag_node`
3. **Execution Nodes**:
   - **`scout_node`**: Fetches live postings, calls Gemini to evaluate alignment with user skills, saves results, and sends high matches to Discord.
   - **`planner_node`**: Prompts Gemini to return structured JSON roadmaps and saves them.
   - **`rag_node`**: Searches LanceDB for the 3 most relevant text chunks using cosine similarity, then passes them to Gemini to synthesize an answer.

*Note: If LangGraph isn't installed or fails, there is a simple sequential fallback script that runs the exact same functions in order.*

---

## 🛠️ Tech Stack

* **Frontend:** Streamlit
* **Backend:** FastAPI, Uvicorn
* **State & Flow:** LangGraph
* **LLM:** Google Gemini Flash (`google-genai`)
* **Vector Store & Embeddings:** LanceDB + FastEmbed (`BAAI/bge-small-en-v1.5` running locally via ONNX)
* **Document Processing:** PyMuPDF (`fitz`)
* **Relational Database:** SQLite via SQLAlchemy
* **Background Tasks:** APScheduler
* **Notifications:** Discord Webhooks (`discord-webhook`)

---

## 📁 Repository Structure

```text
pathfinder-agent/
├── backend/
│   └── main.py              # FastAPI app, API routes, app startup/shutdown
├── agent/
│   ├── graph.py             # LangGraph StateGraph setup
│   └── nodes.py             # Shared state definition and node logic
├── services/
│   ├── gemini.py            # Gemini calls for scoring, RAG, and planning
│   ├── opportunities.py     # Logic to fetch, parse, score, and save jobs
│   ├── discord.py           # Discord webhook triggers and notification logging
│   └── logger.py            # Structured console logging
├── memory/
│   ├── sqlite.py            # SQLAlchemy setup and database helper functions
│   └── lancedb.py           # LanceDB tables, embedding generation, and vector search
├── rag/
│   └── ingest.py            # File text extraction, splitting, and vector ingestion
├── scheduler/
│   └── jobs.py              # Background job setup using APScheduler
├── models/
│   └── schemas.py           # SQLAlchemy tables and Pydantic validation schemas
├── frontend/
│   └── app.py               # Multi-page Streamlit interface
├── data/
│   ├── pathfinder.db        # Local SQLite database file
│   └── lancedb/             # Local LanceDB vector store directory
├── uploads/                 # Uploaded PDFs and notes
├── .env.example             # Example environment variables
└── requirements.txt         # Project dependencies
```

---

## 🚀 Getting Started

### Prerequisites

* Python 3.10 or higher
* A Gemini API key (from Google AI Studio)
* A Discord Webhook URL (optional, if you want live alerts)

### 1. Clone & Setup Virtual Environment

```bash
git clone https://github.com/basilpeter01/pathfinder-agent.git
cd pathfinder-agent

# Create virtual environment
python -m venv venv

# Activate it
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory:

```bash
# On Windows
copy .env.example .env

# On Linux/macOS
cp .env.example .env
```

Add your details inside `.env`:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash                       # optional, defaults to flash
DISCORD_WEBHOOK_URL=your_discord_webhook_url_here  # optional
SCOUT_INTERVAL_MINUTES=5
DISCORD_SCORE_THRESHOLD=85
```

### 3. Run the Project

**Terminal 1 (Backend API):**

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 (Frontend Interface):**

```bash
streamlit run frontend/app.py
```

* Streamlit UI runs at: `http://localhost:8501`
* FastAPI Swagger docs run at: `http://127.0.0.1:8000/docs`

---

## 💡 Practical Design Choices

* **Local Embeddings with FastEmbed:** Instead of paying for an embedding API or hitting rate limits, embeddings run completely offline on CPU using ONNX.
* **Embedded Vector Storage with LanceDB:** LanceDB stores vectors locally on disk without needing a separate Docker container or heavy server setup like Pinecone or Milvus.
* **Zero-Setup Database:** SQLite comes built into Python, keeping the setup minimal while still using SQLAlchemy models in case I want to migrate to PostgreSQL later.
* **Fallbacks:** If no Gemini API key is provided, the scoring logic falls back to a simple keyword-matching heuristic so the app doesn't crash during testing. If no Discord webhook is provided, alerts simply log to SQLite. If LangGraph is not installed, it falls back to a simple sequential execution of the nodes.