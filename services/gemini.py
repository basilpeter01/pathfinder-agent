import os
import json
import time
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

try:
    from google import genai
    _HAS_GENAI = True
except ImportError:
    _HAS_GENAI = False

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

def _is_api_key_valid() -> bool:
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here" or "your_" in GEMINI_API_KEY:
        return False
    return _HAS_GENAI

def _get_client() -> Optional[Any]:
    if not _is_api_key_valid():
        return None
    try:
        return genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Warning: Failed to create Google GenAI client: {e}")
        return None

def _generate_content_with_retry(client: Any, prompt: str, max_retries: int = 3) -> str:
    """Helper to call Gemini API with automatic retry on SSL/network drops or transient errors."""
    last_err = None
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
            return response.text.strip()
        except Exception as e:
            last_err = e
            err_str = str(e)
            if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                raise e
            print(f"[Gemini API Retry {attempt+1}/{max_retries}] Network/SSL drop ({e}). Retrying...")
            time.sleep(1.5 * (attempt + 1))
    raise last_err

def score_opportunity_with_llm(user_profile: Dict[str, Any], opp: Dict[str, Any], use_llm: bool = True) -> Dict[str, Any]:
    """Score an opportunity against user profile using Gemini or fallback rule-based engine."""
    title = opp.get("title", "")
    company = opp.get("company", "")
    skills = user_profile.get("skills", "")
    interests = user_profile.get("interests", "")
    domains = user_profile.get("preferred_domains", "")

    client = _get_client() if use_llm else None
    if not client:
        # Fallback heuristic scoring when API key is missing or invalid
        score = 50.0
        reasons = []
        lower_title = title.lower()
        lower_skills = skills.lower()
        lower_interests = interests.lower()
        
        if "ai" in lower_title or "ml" in lower_title or "agent" in lower_title or "machine learning" in lower_title:
            score += 35.0
            reasons.append("Strong alignment with AI & Machine Learning goals")
        if "backend" in lower_title or "python" in lower_title or "data" in lower_title:
            score += 25.0
            reasons.append("Matches preferred backend & python skills")
        if "hackathon" in lower_title or "capstone" in lower_title:
            score += 20.0
            reasons.append("Direct hit for hackathon & competition interests")
        if "flutter" in lower_title or "mobile" in lower_title:
            score -= 25.0
            reasons.append("Low relevance to preferred AI & Backend domains")
            
        final_score = min(max(round(score, 1), 10.0), 98.0)
        reason_str = "; ".join(reasons) if reasons else "Moderate match based on profile domain keywords."
        return {"score": final_score, "reason": f"[Rule Fallback] {reason_str}"}

    try:
        prompt = (
            f"Score this job opportunity for a student (0-100). "
            f"Skills: {skills[:120]}. Domains: {domains[:80]}.\n"
            f"Job: {title} at {company}.\n"
            f"Reply ONLY with JSON: {{\"score\": <int>, \"reason\": \"<1 sentence>\"}}"
        )
        text = _generate_content_with_retry(client, prompt)
        if text.startswith("```json"):
            text = text[7:-3].strip()
        elif text.startswith("```"):
            text = text[3:-3].strip()
        data = json.loads(text)
        return {"score": float(data.get("score", 65.0)), "reason": str(data.get("reason", "AI evaluated match."))}
    except Exception as e:
        print(f"Gemini evaluation error: {e}. Using fallback.")
        return {"score": 75.0, "reason": f"[Offline Fallback] Good potential match for {domains}."}

def answer_question_with_rag(question: str, context_chunks: List[str]) -> str:
    """Answer a user question based strictly on provided RAG context chunks."""
    if not context_chunks:
        return "No relevant information found in uploaded documents. Please upload study PDFs or check your query."
    
    context_text = "\n\n---\n\n".join(context_chunks)
    
    client = _get_client()
    if not client:
        return f"[Offline RAG Preview] Found {len(context_chunks)} relevant chunk(s) in your Knowledge Vault matching '{question}':\n\n1. {context_chunks[0][:300]}...\n\n(Configure GEMINI_API_KEY in .env for full synthesized LLM answers!)"

    try:
        # Limit context to first 1500 chars to reduce token usage
        context_trimmed = context_text[:1500]
        prompt = (
            f"Answer using ONLY the context below. If not found, say so.\n"
            f"Context: {context_trimmed}\n"
            f"Question: {question}\nAnswer:"
        )
        return _generate_content_with_retry(client, prompt)
    except Exception as e:
        return f"[RAG Error: {e}] Relevant context excerpt: {context_chunks[0][:250]}..."

def generate_learning_roadmap(topic: str, weeks: int = 4) -> Dict[str, Any]:
    """Generate a structured study roadmap for a given topic."""
    client = _get_client()
    if not client:
        # Fallback structured roadmap
        return {
            "topic": topic,
            "prerequisites": ["Basic Python programming", "Git fundamentals", "Command line basics"],
            "weekly_roadmap": [
                {"week": 1, "focus": f"Core concepts & architecture of {topic}", "tasks": ["Read official documentation", "Set up local environment", "Hello world tutorial"]},
                {"week": 2, "focus": f"Advanced features & best practices in {topic}", "tasks": ["Build REST endpoints or pipelines", "Integrate data storage", "Handle errors gracefully"]},
                {"week": 3, "focus": f"Integration & Project implementation", "tasks": ["Connect with external APIs", "Write unit tests", "Optimize performance"]},
                {"week": 4, "focus": f"Deployment & Capstone project polish", "tasks": ["Deploy to staging/cloud", "Add user authentication", "Finalize presentation documentation"]}
            ],
            "mini_projects": [f"{topic} CLI Assistant", f"Fullstack {topic} Dashboard"],
            "resources": [f"Official {topic} Docs", "Google AI Agents Bootcamp", "Kaggle Tutorials"]
        }

    try:
        prompt = (
            f"{weeks}-week JSON roadmap for: {topic}.\n"
            f"Return ONLY this JSON schema (no extra text):\n"
            f'{{"topic":"{topic}","prerequisites":["str"],'
            f'"weekly_roadmap":[{{"week":1,"focus":"str","tasks":["str"]}}],'
            f'"mini_projects":["str"],"resources":["str"]}}'
        )
        text = _generate_content_with_retry(client, prompt)
        if text.startswith("```json"):
            text = text[7:-3].strip()
        elif text.startswith("```"):
            text = text[3:-3].strip()
        return json.loads(text)
    except Exception as e:
        print(f"Roadmap generation error: {e}")
        return {
            "topic": topic,
            "prerequisites": ["Python basics"],
            "weekly_roadmap": [{"week": 1, "focus": f"Introduction to {topic}", "tasks": ["Read docs", "Practice examples"]}],
            "mini_projects": [f"{topic} Mini App"],
            "resources": ["Official Documentation"]
        }
