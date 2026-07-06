import os
import json
import requests
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from models.schemas import OpportunitySchema, OpportunityDB
from memory.sqlite import get_user_profile, save_opportunities_to_db, get_stored_opportunities
from services.gemini import score_opportunity_with_llm
from services.discord import send_discord_notification

SAMPLE_JSON_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sample_opportunities.json")

def load_sample_opportunities() -> List[Dict[str, Any]]:
    """Load mock opportunities from JSON and label source as Local Memory."""
    if not os.path.exists(SAMPLE_JSON_PATH):
        return []
    try:
        with open(SAMPLE_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                src = item.get("source", "Curated")
                if not src.startswith("Local Memory"):
                    item["source"] = f"Local Memory ({src})"
            return data
    except Exception as e:
        print(f"Error reading sample opportunities: {e}")
        return []

def fetch_live_web_opportunities() -> List[Dict[str, Any]]:
    """Fetch live tech opportunities, hackathons, and open-source challenges from public web APIs."""
    live_opps = []
    headers = {"User-Agent": "Pathfinder-AI-Agent/1.0 (Student Capstone Project)"}
    
    # 1. Fetch live open-source hackathons & AI competitions from GitHub Search API
    try:
        gh_url = "https://api.github.com/search/repositories?q=topic:hackathon+language:python&sort=updated&order=desc&per_page=4"
        res = requests.get(gh_url, headers=headers, timeout=6)
        if res.status_code == 200:
            data = res.json()
            for item in data.get("items", [])[:4]:
                live_opps.append({
                    "title": f"{item.get('name', 'Hackathon').replace('-', ' ').title()} Open Challenge",
                    "company": f"GitHub Org: {item.get('owner', {}).get('login', 'Community')}",
                    "url": item.get("html_url", "https://github.com"),
                    "source": "GitHub Live Open Source API",
                    "deadline": "2026-09-15"
                })
    except Exception as e:
        print(f"[Live Web Fetch Warning] GitHub API unreachable: {e}")

    # 2. Fetch live remote tech jobs & engineering internships from Remotive Public API
    try:
        rm_url = "https://remotive.com/api/remote-jobs?category=software-dev&limit=4"
        res = requests.get(rm_url, headers=headers, timeout=6)
        if res.status_code == 200:
            data = res.json()
            for item in data.get("jobs", [])[:4]:
                live_opps.append({
                    "title": item.get("title", "Software Engineer / Intern"),
                    "company": item.get("company_name", "Tech Company"),
                    "url": item.get("url", "https://remotive.com"),
                    "source": "Remotive Live Web API",
                    "deadline": str(item.get("publication_date", "2026-08-30"))[:10]
                })
    except Exception as e:
        print(f"[Live Web Fetch Warning] Remotive API unreachable: {e}")

    return live_opps

def run_opportunity_scout_pipeline(db: Session) -> List[OpportunityDB]:
    """Autonomous Opportunity Scout Pipeline: Fetch Live -> AI Evaluate -> Rank -> Save -> Notify & Log."""
    print("[Scout Pipeline] Attempting to fetch live opportunities from public web APIs...")
    raw_opps = fetch_live_web_opportunities()
    
    # If offline or rate-limited, fall back to curated sample dataset
    if not raw_opps:
        print("[Scout Pipeline] Live fetch returned 0 items (offline or rate limit). Falling back to local sample dataset.")
        raw_opps = load_sample_opportunities()
    else:
        print(f"[Scout Pipeline] Successfully fetched {len(raw_opps)} live opportunities from web APIs!")
        # Append 2 core curated capstone challenges so the student always has foundational hackathon entries
        sample = load_sample_opportunities()
        if sample:
            raw_opps.extend(sample[:2])
            
    if not raw_opps:
        return []
    
    user = get_user_profile(db)
    user_dict = {
        "skills": user.skills,
        "interests": user.interests,
        "preferred_domains": user.preferred_domains,
        "preferred_location": user.preferred_location
    }
    
    scored_opps = []
    for opp in raw_opps:
        eval_res = score_opportunity_with_llm(user_dict, opp)
        schema = OpportunitySchema(
            title=opp.get("title", "Untitled"),
            company=opp.get("company", "Unknown"),
            url=opp.get("url", "https://example.com"),
            source=opp.get("source", "Scout"),
            deadline=opp.get("deadline", "2026-12-31"),
            score=eval_res["score"],
            reason=eval_res["reason"],
            is_notified=False
        )
        scored_opps.append(schema)
        
    # Sort descending by score
    scored_opps.sort(key=lambda x: x.score, reverse=True)
    
    # Persist in SQLite
    saved_db_list = save_opportunities_to_db(db, scored_opps)
    
    # Check notifications & logging (Phase 10)
    for db_opp in saved_db_list:
        if not db_opp.is_notified and db_opp.score >= 85.0:
            schema_for_notif = OpportunitySchema.from_orm(db_opp) if hasattr(OpportunitySchema, "from_orm") else OpportunitySchema(
                title=db_opp.title,
                company=db_opp.company,
                url=db_opp.url,
                source=db_opp.source,
                deadline=db_opp.deadline,
                score=db_opp.score,
                reason=db_opp.reason,
                is_notified=db_opp.is_notified
            )
            notified = send_discord_notification(db, schema_for_notif)
            if notified:
                db_opp.is_notified = True
                db.commit()
                
    # Sort returned DB list by score
    saved_db_list.sort(key=lambda x: x.score, reverse=True)
    return saved_db_list
