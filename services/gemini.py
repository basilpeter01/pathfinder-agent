import os
import json
import time
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from services.logger import log_event

try:
    from google import genai
    _HAS_GENAI = True
except ImportError:
    _HAS_GENAI = False

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

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
        log_event("WARNING", "GEMINI", f"Failed to create Google GenAI client: {e}")
        return None

def _generate_content_with_retry(client: Any, prompt: str, max_retries: int = 2) -> str:
    """Helper to call Gemini API with automatic model failover and retry on network drops."""
    global GEMINI_MODEL
    candidate_models = []
    for m in [GEMINI_MODEL, "gemini-3.6-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
        if m and m not in candidate_models:
            candidate_models.append(m)

    last_err = None
    for model_name in candidate_models:
        for attempt in range(max_retries):
            t0 = time.time()
            prompt_preview = prompt.replace("\n", " ").strip()[:50]
            log_event("INFO", "GEMINI", f"Outbound call -> model: '{model_name}' | prompt: \"{prompt_preview}...\"")
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                latency_ms = int((time.time() - t0) * 1000)
                resp_text = response.text.strip()
                log_event("INFO", "GEMINI", f"Request completed: {model_name} ({latency_ms}ms, chars: {len(resp_text)})")
                if model_name != GEMINI_MODEL:
                    log_event("INFO", "GEMINI", f"Auto-switched active model to: '{model_name}'")
                    GEMINI_MODEL = model_name
                return resp_text
            except Exception as e:
                latency_ms = int((time.time() - t0) * 1000)
                last_err = e
                err_str = str(e)
                log_event("ERROR", "GEMINI", f"Request failed: {model_name} ({latency_ms}ms) | error: {err_str[:120]}")
                # If model is deprecated or not found, fail over to the next candidate model immediately
                if any(k in err_str for k in ["NOT_FOUND", "404", "no longer available", "is not found"]):
                    log_event("WARNING", "GEMINI", f"Model '{model_name}' unavailable. Attempting failover...")
                    break
                if any(k in err_str for k in ["RESOURCE_EXHAUSTED", "429", "API_KEY_INVALID", "PERMISSION_DENIED", "401", "403"]):
                    raise e
                log_event("WARNING", "GEMINI", f"Retry {attempt+1}/{max_retries} scheduled in {(attempt+1)}s...")
                time.sleep(1.0 * (attempt + 1))

    if last_err is not None:
        raise last_err
    raise RuntimeError("Gemini API call failed with no response or error recorded.")

def score_opportunity_with_llm(user_profile: Dict[str, Any], opp: Dict[str, Any], use_llm: bool = True) -> Dict[str, Any]:
    """Score an opportunity against user profile using Gemini or fallback rule-based engine."""
    title = opp.get("title", "")
    company = opp.get("company", "")
    skills = user_profile.get("skills", "")
    interests = user_profile.get("interests", "")
    domains = user_profile.get("preferred_domains", "")

    client = _get_client() if use_llm else None
    if not client:
        # Dynamic fallback heuristic scoring matching student's profile keywords
        score = 50.0
        reasons = []
        description = opp.get("description", "")
        target_text = f"{title} {company} {description}".lower()
        
        # Split skills, interests, and preferred_domains into distinct keywords
        profile_keywords = set()
        for field_val in [skills, interests, domains]:
            if field_val:
                for part in field_val.replace(";", ",").replace("/", ",").split(","):
                    cleaned = part.strip().lower()
                    if len(cleaned) >= 2:
                        profile_keywords.add(cleaned)
        
        # Calculate score based on keyword overlap between student profile and opportunity
        matched_keywords = [kw for kw in profile_keywords if kw in target_text]
        if matched_keywords:
            score += min(len(matched_keywords) * 12.0, 45.0)
            displayed_matches = ", ".join(sorted(matched_keywords)[:3])
            reasons.append(f"Profile keyword match: {displayed_matches}")
        else:
            reasons.append("Baseline match based on industry domain alignment")
            
        final_score = min(max(round(score, 1), 0.0), 100.0)
        reason_str = "; ".join(reasons)
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
        # Allow full context across retrieved chunks (up to 12000 chars)
        context_trimmed = context_text[:12000]
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
        raise RuntimeError("Gemini API key is not configured. Please configure GEMINI_API_KEY in your .env file to generate AI study roadmaps.")

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
        log_event("ERROR", "GEMINI", f"Roadmap generation failed: {e}")
        raise RuntimeError(f"Roadmap generation failed: {e}")
