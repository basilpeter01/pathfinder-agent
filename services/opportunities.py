import os
import json
import time
import requests
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from models.schemas import OpportunitySchema, OpportunityDB
from memory.sqlite import get_user_profile, save_opportunities_to_db, get_stored_opportunities
from services.gemini import score_opportunity_with_llm
from services.discord import send_discord_notification
from services.logger import log_event



def fetch_live_web_opportunities() -> List[Dict[str, Any]]:
    """Fetch live tech opportunities, hackathons, and open-source challenges from public web APIs."""
    live_opps = []
    headers = {"User-Agent": "Pathfinder-AI-Agent/1.0 (Student Capstone Project)"}
    
    # 1. Fetch live open-source hackathons & AI competitions from GitHub Search API
    try:
        gh_url = "https://api.github.com/search/repositories?q=topic:hackathon+language:python&sort=updated&order=desc&per_page=4"
        t0 = time.time()
        log_event("INFO", "SCOUT", "Outbound request -> GET api.github.com (query: hackathons)")
        res = requests.get(gh_url, headers=headers, timeout=6)
        dur = int((time.time() - t0) * 1000)
        if res.status_code == 200:
            data = res.json()
            items = data.get("items", [])[:4]
            log_event("INFO", "SCOUT", f"GitHub Search API returned {len(items)} hackathons (HTTP 200, {dur}ms)")
            for item in items:
                live_opps.append({
                    "title": f"{item.get('name', 'Hackathon').replace('-', ' ').title()} Open Challenge",
                    "company": f"GitHub Org: {item.get('owner', {}).get('login', 'Community')}",
                    "url": item.get("html_url", "https://github.com"),
                    "source": "GitHub Live Open Source API",
                    "deadline": "Rolling"
                })
        else:
            log_event("WARNING", "SCOUT", f"GitHub Search API returned HTTP {res.status_code} ({dur}ms)")
    except Exception as e:
        log_event("ERROR", "SCOUT", f"GitHub Search API unreachable | error: {e}")

    # 2. Fetch live remote tech jobs & engineering internships from Remotive Public API
    try:
        rm_url = "https://remotive.com/api/remote-jobs?category=software-dev&limit=4"
        t0 = time.time()
        log_event("INFO", "SCOUT", "Outbound request -> GET remotive.com (category: software-dev)")
        res = requests.get(rm_url, headers=headers, timeout=6)
        dur = int((time.time() - t0) * 1000)
        if res.status_code == 200:
            data = res.json()
            jobs = data.get("jobs", [])[:4]
            log_event("INFO", "SCOUT", f"Remotive Jobs API returned {len(jobs)} jobs (HTTP 200, {dur}ms)")
            for item in jobs:
                pub_date = item.get("publication_date")
                deadline_str = str(pub_date)[:10] if pub_date else "Rolling / Open"
                live_opps.append({
                    "title": item.get("title", "Software Engineer / Intern"),
                    "company": item.get("company_name", "Tech Company"),
                    "url": item.get("url", "https://remotive.com"),
                    "source": "Remotive Live Web API",
                    "deadline": deadline_str
                })
        else:
            log_event("WARNING", "SCOUT", f"Remotive API returned HTTP {res.status_code} ({dur}ms)")
    except Exception as e:
        log_event("ERROR", "SCOUT", f"Remotive API unreachable | error: {e}")

    return live_opps

def run_opportunity_scout_pipeline(db: Session, use_llm: bool = False) -> List[OpportunityDB]:
    """Autonomous Opportunity Scout Pipeline: Fetch Live -> AI Evaluate -> Rank -> Save -> Notify & Log."""
    log_event("INFO", "SCOUT", "Executing opportunity scout pipeline...")
    raw_opps = fetch_live_web_opportunities()
    
    if not raw_opps:
        log_event("WARNING", "SCOUT", "Live web fetch returned 0 opportunities (network issue, offline, or API rate limit).")
        return []
        
    log_event("INFO", "SCOUT", f"Successfully fetched {len(raw_opps)} live opportunities from web APIs")
    
    user = get_user_profile(db)
    user_dict = {
        "skills": user.skills,
        "interests": user.interests,
        "preferred_domains": user.preferred_domains,
        "preferred_location": user.preferred_location
    }
    
    scored_opps = []
    for idx, opp in enumerate(raw_opps):
        # Use LLM only for top 2 in manual scout mode; always heuristic in background mode
        should_use_llm = use_llm and (idx < 2)
        if should_use_llm and idx > 0:
            time.sleep(3.0)  # Rate limit pause between LLM requests (manual scout only)
        eval_res = score_opportunity_with_llm(user_dict, opp, use_llm=should_use_llm)
        schema = OpportunitySchema(
            title=opp.get("title", "Untitled"),
            company=opp.get("company", "Unknown"),
            url=opp.get("url", "https://example.com"),
            source=opp.get("source", "Scout"),
            deadline=opp.get("deadline", "Rolling / Open"),
            score=eval_res["score"],
            reason=eval_res["reason"],
            is_notified=False
        )
        scored_opps.append(schema)
        
    # Sort descending by score
    scored_opps.sort(key=lambda x: x.score, reverse=True)
    
    # Persist in SQLite
    saved_db_list = save_opportunities_to_db(db, scored_opps)
    log_event("INFO", "SCOUT", f"Persisted {len(saved_db_list)} ranked opportunities into database")
    
    # Check notifications & logging (Phase 10)
    for db_opp in saved_db_list:
        if not db_opp.is_notified:
            if db_opp.score >= 85.0:
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
            else:
                log_event("INFO", "SCOUT", f"Opportunity score below threshold ({db_opp.score} < 85.0), skipping alert: '{db_opp.title[:35]}'")
                
    # Sort returned DB list by score
    saved_db_list.sort(key=lambda x: x.score, reverse=True)
    return saved_db_list
