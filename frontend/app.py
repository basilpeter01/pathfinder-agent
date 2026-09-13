import os
import streamlit as st
import requests
import json
from typing import Dict, Any, List

# ==========================================
# Page Configuration & Styling
# ==========================================

st.set_page_config(
    page_title="Pathfinder Agent — Event Scout and Knowledge Vault",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Styling for Aesthetics & Dark/Light Mode Compatibility
st.markdown("""
<style>
    div[data-testid="metric-container"] {
        background-color: rgba(28, 131, 225, 0.08);
        border: 1px solid rgba(28, 131, 225, 0.2);
        padding: 15px;
        border-radius: 10px;
        transition: all 0.2s ease;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    h1, h2, h3 {
        font-family: 'Outfit', 'Inter', sans-serif;
        font-weight: 600;
    }
    .score-badge-high {
        background: linear-gradient(135deg, #10b981, #059669);
        color: white;
        padding: 4px 10px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 0.9em;
    }
    .score-badge-med {
        background: linear-gradient(135deg, #f59e0b, #d97706);
        color: white;
        padding: 4px 10px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 0.9em;
    }
    .intent-tag {
        background: rgba(139, 92, 246, 0.2);
        color: #8b5cf6;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8em;
        font-weight: bold;
        text-transform: uppercase;
    }
</style>
""", unsafe_allow_html=True)

API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
st.session_state["connection_error_shown"] = False

def fetch_api(endpoint: str, method: str = "GET", json_data: dict = None, files: dict = None) -> Any:
    url = f"{API_BASE}{endpoint}"
    try:
        if method == "GET":
            res = requests.get(url, timeout=10)
        elif method == "POST":
            if files:
                res = requests.post(url, files=files, timeout=60)
            else:
                # Scout pipeline + scoring can take 20-30s
                res = requests.post(url, json=json_data, timeout=60)
        if res.status_code == 200:
            return res.json()
        else:
            st.error(f"API Error ({res.status_code}): {res.text}")
            return None
    except requests.exceptions.ConnectionError:
        if not st.session_state.get("connection_error_shown"):
            st.error("Cannot connect to Server.")
            st.session_state["connection_error_shown"] = True
        return None
    except Exception as e:
        st.error(f"Error communicating with server: {e}")
        return None

def get_profile_data() -> dict:
    """Fetch profile from backend API, with fallback to local SQLite and session cache if backend is offline."""
    res = fetch_api("/profile")
    if res and isinstance(res, dict):
        st.session_state["cached_profile"] = res
        return res
    if "cached_profile" in st.session_state:
        return st.session_state["cached_profile"]
    # Direct local SQLite fallback if backend server is not running
    try:
        from memory.sqlite import SessionLocal, get_user_profile
        db = SessionLocal()
        user = get_user_profile(db)
        data = {
            "name": user.name or "",
            "skills": user.skills or "",
            "interests": user.interests or "",
            "preferred_domains": user.preferred_domains or "",
            "preferred_location": user.preferred_location or "Remote",
            "notification_preference": user.notification_preference or "Discord"
        }
        db.close()
        st.session_state["cached_profile"] = data
        return data
    except Exception:
        return {}

# ==========================================
# Sidebar Navigation
# ==========================================

with st.sidebar:
    st.image("https://img.icons8.com/clouds/200/compass.png", width=100)
    st.title("Pathfinder Agent")
    st.caption("Autonomous Student Growth Agent")
    st.markdown("---")
    
    nav_options = [
        "Dashboard & Overview",
        "Autonomous AI Agent",
        "Opportunity Scout",
        "Study Knowledge Vault",
        "Learning Planner",
        "Student Profile",
        "Settings & Reference"
    ]
    if "nav_target" in st.session_state:
        st.session_state["nav_radio"] = st.session_state.pop("nav_target")
    elif "nav_radio" not in st.session_state or st.session_state["nav_radio"] not in nav_options:
        st.session_state["nav_radio"] = nav_options[0]
        
    page = st.radio(
        "Navigation",
        nav_options,
        key="nav_radio"
    )
    
    st.markdown("---")
    st.markdown("### System Status")
    health = fetch_api("/health")
    sched_status = fetch_api("/scheduler/status") or {}
    
    if health and health.get("status") == "healthy":
        st.success("● Server: Online")
    else:
        st.error("● Server: Offline")
        
    if sched_status.get("is_running"):
        st.info(f"Scout: Active ({sched_status.get('interval_minutes', 5)}m loop)")
    else:
        st.warning("Scout: Paused")
        
    st.caption("Pathfinder Agent v1.0")

# ==========================================
# 1. Dashboard & Overview Page
# ==========================================
if page == "Dashboard & Overview":
    st.title("Pathfinder Agent")
    st.markdown("Autonomous career and study companion for students.")
    
    with st.spinner("Connecting..."):
        profile = get_profile_data()
        # /opportunities shows what's already stored
        opps = fetch_api("/opportunities") or []
        vault_docs = fetch_api("/vault/documents") or {"count": 0}
        notifs = fetch_api("/notifications") or []
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        skills_raw = profile.get("skills", "")
        skills_count = len([s for s in str(skills_raw).split(",") if s.strip()]) if skills_raw else 0
        st.metric(label="Skills Tracked", value=skills_count)
    with col2:
        st.metric(label="Opportunities Ranked", value=len(opps))
    with col3:
        st.metric(label="Knowledge Vault PDFs", value=vault_docs.get("count", 0))
    with col4:
        st.metric(label="System Alerts Logged", value=len(notifs))
        
    st.markdown("---")
    
    tab_overview, tab_alerts = st.tabs(["Ranked Opportunities", f"Notification Logs ({len(notifs)})"])
    
    with tab_overview:
        left_col, right_col = st.columns([3, 2])
        with left_col:
            st.subheader("Events")
            if opps:
                top_3 = opps[:3]
                for idx, opp in enumerate(top_3):
                    score = opp.get("score", 0)
                    badge_class = "score-badge-high" if score >= 80 else "score-badge-med"
                    with st.container():
                        st.markdown(f"""
                        **{idx+1}. [{opp.get('title')}]({opp.get('url')})** — *{opp.get('company')}*  
                        Deadline: `{opp.get('deadline')}`
                        *{opp.get('reason')}*
                        """, unsafe_allow_html=True)
                        st.divider()
            else:
                st.info("No opportunities ranked at the moment.")
                if st.button("Run Opportunity Scout Now", type="primary"):
                    with st.spinner("Scouting and scoring opportunities..."):
                        res = fetch_api("/run-agent", method="POST")
                        if res:
                            st.success(f"{res.get('message', 'Scout complete')}")
                            st.rerun()
                
        with right_col:
            st.subheader("Active Profile Summary")
            st.write(f"**Name:** `{profile.get('name') or '—'}`")
            st.write(f"**Preferred Domains:** `{profile.get('preferred_domains') or '—'}`")
            st.write(f"**Core Skills:** `{profile.get('skills') or '—'}`")
            st.write(f"**Location Pref:** `{profile.get('preferred_location') or '—'}`")
            if st.button("Edit Profile Settings", use_container_width=True):
                st.session_state["nav_target"] = "Student Profile"
                st.rerun()
                
    with tab_alerts:
        st.subheader("Background Alerts & Notifications")
        st.markdown("Summary of Notifications.")
        if notifs:
            for n in notifs:
                with st.expander(f"`{n.get('timestamp')}` — {n.get('title')}", expanded=False):
                    st.write(f"**Message:** {n.get('message')}")
                    if n.get('url'):
                        st.link_button("Open Opportunity Link", url=n.get('url'), use_container_width=False)
        else:
            st.info("No system notifications logged.")

# ==========================================
# 2. Autonomous AI Agent Chat Page
# ==========================================
elif page == "Autonomous AI Agent":
    st.title("Autonomous AI Assistant")
    st.markdown("""
    Experience Pathfinder's unified **autonomous orchestration engine**. Type anything below, and your assistant will:
    1. **Load Profile**: Fetch your saved skills and career goals from local memory.
    2. **Determine Intent**: Route between **Scout** (internships/hackathons), **Planner** (study roadmaps), or **Knowledge Vault** (PDF study questions).
    """)
    
    if "agent_messages" not in st.session_state:
        st.session_state.agent_messages = [
            {"role": "assistant", "content": "Hello! I am your autonomous Pathfinder Assistant. Try saying:\n- *'Find me internships'*\n- *'Create a study roadmap for Python'*\n- *'Summarize key concepts from my study notes'*", "intent": "system"}
        ]
        
    for msg in st.session_state.agent_messages:
        with st.chat_message(msg["role"]):
            if "intent" in msg and msg["intent"] != "system":
                st.markdown(f"<span class='intent-tag'>Agent Route: {msg['intent'].upper()}</span>", unsafe_allow_html=True)
            st.markdown(msg["content"])
            
    if user_prompt := st.chat_input("Command your autonomous Agent..."):
        st.session_state.agent_messages.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)
            
        with st.chat_message("assistant"):
            with st.spinner("Analyzing request and executing..."):
                res = fetch_api("/agent/chat", method="POST", json_data={"user_input": user_prompt})
                if res:
                    intent_routed = res.get("intent", "unknown")
                    response_text = res.get("response", "No response generated.")
                    st.markdown(f"<span class='intent-tag'>Agent Route: {intent_routed.upper()}</span>", unsafe_allow_html=True)
                    st.markdown(response_text)
                    st.session_state.agent_messages.append({"role": "assistant", "content": response_text, "intent": intent_routed})

# ==========================================
# 3. Student Profile Page
# ==========================================
elif page == "Student Profile":
    st.title("Student Profile & Interest Preferences")
    st.markdown("Customize your skills and domains.")
    
    current_profile = get_profile_data()
    
    with st.form("profile_form"):
        name = st.text_input("Full Name", value=current_profile.get("name", ""))
        skills = st.text_area("Core Skills (Comma separated)", value=current_profile.get("skills", ""), placeholder="e.g. Python, SQL, Machine Learning")
        interests = st.text_area("Passions & Interests", value=current_profile.get("interests", ""), placeholder="e.g. Open Source, Cloud Architecture, AI Agents")
        DOMAIN_OPTIONS = [
            "Artificial Intelligence", "Machine Learning", "Data Science", 
            "Full Stack Web Development", "Frontend Development", "Backend Development", 
            "Mobile App Development", "DevOps & SRE", "Cloud Computing", 
            "Cybersecurity", "Game Development", "Embedded Systems & IoT", 
            "Blockchain & Web3", "Natural Language Processing", "UI/UX Design"
        ]
        
        current_domains = [d.strip() for d in current_profile.get("preferred_domains", "").split(",") if d.strip() in DOMAIN_OPTIONS]
        selected_domains = st.multiselect(
            "Preferred Career Domains",
            options=DOMAIN_OPTIONS,
            default=current_domains
        )
        preferred_domains = ", ".join(selected_domains)
        
        pref_loc = current_profile.get("preferred_location", "Remote")
        loc_options = ["Remote", "Hybrid", "On-site", "Remote / Hybrid"]
        loc_index = loc_options.index(pref_loc) if pref_loc in loc_options else 0
        preferred_location = st.selectbox(
            "Preferred Work Location",
            loc_options,
            index=loc_index
        )
        
        notif_val = current_profile.get("notification_preference", "Discord")
        notif_options = ["Discord", "Email", "In-App Only"]
        notif_index = notif_options.index(notif_val) if notif_val in notif_options else 0
        notification_pref = st.selectbox(
            "Notification Preference",
            notif_options,
            index=notif_index
        )
        
        submit = st.form_submit_button("Save Profile & Update Recommendations")
        if submit:
            payload = {
                "name": name,
                "skills": skills,
                "interests": interests,
                "preferred_domains": preferred_domains,
                "preferred_location": preferred_location,
                "notification_preference": notification_pref
            }
            res = fetch_api("/profile", method="POST", json_data=payload)
            if res:
                st.session_state["cached_profile"] = res
                st.success("Profile updated and saved to local memory.")
            else:
                # Direct SQLite persistence fallback if backend is offline
                try:
                    from memory.sqlite import SessionLocal, update_user_profile
                    from models.schemas import ProfileSchema
                    db = SessionLocal()
                    update_user_profile(db, ProfileSchema(**payload))
                    db.close()
                    st.session_state["cached_profile"] = payload
                    st.success("Profile saved.")
                except Exception as e:
                    st.error(f"Could not save profile: {e}")

# ==========================================
# 4. Opportunity Scout Page
# ==========================================
elif page == "Opportunity Scout":
    st.title("Autonomous Opportunity Scout")
    st.markdown("Pathfinder wakes up, scouts internships and hackathons, removes duplicates, and uses **Gemini LLM reasoning** to rank each opportunity against your interest scores.")
    
    col_btn, col_txt = st.columns([1, 4])
    with col_btn:
        run_scout = st.button("Run Agent Now", use_container_width=True, type="primary")
    with col_txt:
        st.caption("Click to trigger an autonomous scouting, ranking, and optional Discord webhook alerting pass.")
        
    if run_scout:
        with st.spinner("Agent scouting and scoring opportunities..."):
            res = fetch_api("/run-agent", method="POST")
            if res:
                st.success(f"{res.get('message')}")
                st.rerun()
                
    st.markdown("---")
    
    opps = fetch_api("/opportunities") or []
    if opps:
        st.subheader(f"Ranked Opportunities ({len(opps)} found)")
        for opp in opps:
            score = opp.get("score", 0)
            badge_color = "#10b981" if score >= 85 else ("#f59e0b" if score >= 65 else "#64748b")
            
            with st.expander(f"{opp.get('title')} — {opp.get('company')}", expanded=(score >= 80)):
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.markdown(f"**Company / Sponsor:** `{opp.get('company')}`")
                    st.markdown(f"**Source:** `{opp.get('source')}` &nbsp; | &nbsp; **Deadline:** `{opp.get('deadline')}`")   
                with col_b:
                    st.link_button("View Opportunity", url=opp.get("url", "#"), use_container_width=True)
    else:
        st.info("No opportunities found.")

# ==========================================
# 5. Study Knowledge Vault Page
# ==========================================
elif page == "Study Knowledge Vault":
    st.title("Study Knowledge Vault (AI Assistant)")
    st.markdown("Upload lecture notes, papers, or documentation files.")
    
    col_up, col_list = st.columns([2, 1])
    with col_up:
        st.subheader("Upload Study Document")
        uploaded_file = st.file_uploader("Choose a file", type=["pdf", "txt", "md"])
        if uploaded_file is not None:
            if st.button("Index into Study Vault", type="primary"):
                with st.spinner(f"Extracting text and indexing `{uploaded_file.name}`..."):
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                    res = fetch_api("/upload", method="POST", files=files)
                    if res and res.get("status") == "success":
                        st.success(f"Successfully indexed {res.get('chunks_ingested')} text chunks")
                    elif res and res.get("status") == "error":
                        st.error(f"{res.get('message')}")
                    else:
                        st.error("Failed to index document.")
                        
    with col_list:
        st.subheader("Ingested Documents")
        vault_docs = fetch_api("/vault/documents") or {"documents": [], "count": 0}
        if vault_docs["documents"]:
            for d in vault_docs["documents"]:
                st.write(f"`{d}`")
        else:
            st.caption("No study files uploaded yet.")
            
    st.markdown("---")
    st.subheader("Ask Your Knowledge Vault")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
        
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "sources" in message and message["sources"]:
                st.caption(f"Cited Sources: {', '.join(message['sources'])}")
                
    if prompt := st.chat_input("Ask a question about your uploaded study notes..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            
        with st.chat_message("assistant"):
            with st.spinner("Searching study vectors..."):
                res = fetch_api("/ask", method="POST", json_data={"question": prompt})
                if res:
                    ans = res.get("answer", "No answer generated.")
                    srcs = res.get("sources", [])
                    st.markdown(ans)
                    if srcs:
                        st.caption(f"Cited Sources: {', '.join(srcs)}")
                    st.session_state.messages.append({"role": "assistant", "content": ans, "sources": srcs})

# ==========================================
# 6. Learning Planner Page
# ==========================================
elif page == "Learning Planner":
    st.title("AI Learning Planner")
    st.markdown("Input any technical skill or topic for a roadmap with prerequisites, tasks, and portfolio projects.")
    
    tab_gen, tab_saved = st.tabs(["Generate New Roadmap", "Saved Roadmaps"])
    
    with tab_gen:
        with st.form("roadmap_form"):
            col1, col2 = st.columns([3, 1])
            with col1:
                topic = st.text_input("Topic to Learn", placeholder="e.g., Web Development, Artificial Intelligence, Mobile Apps, or Cloud Computing")
            with col2:
                duration = st.slider("Duration (Weeks)", min_value=1, max_value=8, value=4)
                
            gen_btn = st.form_submit_button("Generate AI Roadmap", type="primary")
            if gen_btn and topic:
                with st.spinner(f"Creating and saving a custom {duration}-week study plan for '{topic}'..."):
                    res = fetch_api("/roadmap", method="POST", json_data={"topic": topic, "duration_weeks": duration})
                    if res:
                        st.session_state["active_roadmap"] = res
                        st.success("Roadmap generated and saved to your personal library!")
                        
        if "active_roadmap" in st.session_state:
            rm = st.session_state["active_roadmap"]
            st.markdown(f"## Study Roadmap: **{rm.get('topic')}**")
            
            st.subheader("Prerequisites")
            for p in rm.get("prerequisites", []):
                st.markdown(f"- `{p}`")
                
            st.subheader("Weekly Timeline")
            for w in rm.get("weekly_roadmap", []):
                with st.expander(f"Week {w.get('week', '')}: {w.get('focus', '')}", expanded=True):
                    for t in w.get("tasks", []):
                        st.markdown(f"  - {t}")
                        
            col_proj, col_res = st.columns(2)
            with col_proj:
                st.subheader("Hands-On Portfolio Projects")
                for proj in rm.get("mini_projects", []):
                    st.markdown(f"- **{proj}**")
            with col_res:
                st.subheader("Recommended Resources")
                for r in rm.get("resources", []):
                    st.markdown(f"- `{r}`")
                    
    with tab_saved:
        st.subheader("Previously Saved Study Roadmaps")
        saved_rms = fetch_api("/roadmaps") or []
        if saved_rms:
            for r in saved_rms:
                with st.expander(f"Roadmap: {r.get('topic')}"):
                    st.code(r.get('content'), language="json")
        else:
            st.info("No roadmaps saved yet.")

# ==========================================
# 7. Settings & Reference Page
# ==========================================
elif page == "Settings & Reference":
    st.title("System Settings & Quick Reference")
    st.markdown("Manage your network connection and background automation frequency.")
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Server Connection Settings")
        st.code(f"Server URL: {API_BASE}", language="text")
        st.caption("Change via API_BASE_URL environment variable if running on a custom network host.")
    with col_b:
        st.subheader("Autonomous Scouting Control")
        if st.button("Trigger Scouting Pass Now", use_container_width=True):
            res = fetch_api("/scheduler/trigger", method="POST")
            if res:
                st.success(f"{res.get('message')}")
    
    st.markdown("---")
    st.subheader("Quick Reference & Setup Guide")
    st.markdown("""
    1. **AI Intelligence Key**: To unlock live LLM reasoning, get a free API key at [Google AI Studio](https://aistudio.google.com/) and add it to `.env` as `GEMINI_API_KEY`.
    2. **Discord Alerts**: To receive real-time webhook notifications on your mobile device, add your Discord channel webhook URL to `.env` as `DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...`.
    3. **Local Memory Storage**: All profile preferences, learning roadmaps, and study vectors are stored on your device.
    4. **Server Status**: Both the Server and UI run independently to ensure responsiveness and UI updates.
    """)
