from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import sqlite3
import os
import json
import httpx
from datetime import date

app = FastAPI(title="Divya's Germany Companion API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── CONFIG ─────────────────────────────────────────────
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

# Best free-tier model order: highest RPD first
GEMINI_MODELS = [
    "gemini-2.0-flash",               # primary workhorse
    "gemini-1.5-flash",               # fallback
    "gemini-1.5-flash-8b",            # last resort
]

DB_PATH = "companion.db"

# ─── SYSTEM PROMPT ──────────────────────────────────────
SYSTEM_PROMPT = """
You are Mia — Divya's personal AI companion, study buddy, and career coach in Germany.

About Divya:
- Name: Divya
- Goal: Land a Werkstudent Data Analyst or IT role in Germany during her Master's
- Background: 2.5 years as Product Support Analyst (Infor IBMi) — she knows GL, FSM, ServiceNow, incident management
- Skills: SQL (basic), Excel (intermediate), business application knowledge
- She wants to work in a proper IT/Data role, NOT restaurants or retail

Your personality:
- Warm, encouraging, like a smart best friend who genuinely cares
- Practical — give specific steps, not vague advice
- Celebrate her wins, no matter how small
- Remind her she is more capable than she thinks

Current mode: {mode}

Always structure your response:
1. One warm, personal line (acknowledge what she said)
2. Clear, direct answer or guidance
3. 2–3 specific, actionable next steps she can do TODAY or THIS WEEK

For career/job topics always mention:
- Specific platforms: LinkedIn, StepStone, Indeed.de, Xing, Glassdoor.de, university job boards
- Konkret roles she qualifies for given her background
- That her 2.5 years IT experience is a real advantage — most students don't have it

For study topics:
- Break it down simply
- Suggest free resources (Coursera, YouTube, W3Schools, Mode Analytics for SQL)

For emotional/overwhelm topics:
- Be warm and human first, then practical
- Remind her that struggling is normal and temporary

Never give generic advice. Always tie it back to Divya's specific situation.
""".strip()

# ─── DATABASE ───────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS user_profile (
        id INTEGER PRIMARY KEY,
        name TEXT DEFAULT 'Divya',
        goal TEXT DEFAULT 'Get a Werkstudent Data Analyst job in Germany',
        skills TEXT DEFAULT 'SQL (basic), Excel (intermediate), ServiceNow, IBMi',
        experience TEXT DEFAULT '2.5 years Product Support Analyst (Infor IBMi)',
        target_role TEXT DEFAULT 'Data Analyst / IT Werkstudent',
        city TEXT DEFAULT 'Germany',
        university TEXT DEFAULT ''
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT,
        content TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS progress_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        log_date TEXT,
        jobs_applied INTEGER DEFAULT 0,
        study_hours REAL DEFAULT 0,
        mood INTEGER DEFAULT 3,
        note TEXT DEFAULT ''
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS tip_cache (
        id INTEGER PRIMARY KEY,
        tip_date TEXT,
        tip_text TEXT
    )
    """)

    c.execute("INSERT OR IGNORE INTO user_profile (id) VALUES (1)")
    c.execute("INSERT OR IGNORE INTO tip_cache (id, tip_date, tip_text) VALUES (1, '', '')")
    conn.commit()
    conn.close()

def get_profile():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, goal, skills, experience, target_role, city, university FROM user_profile WHERE id=1")
    row = c.fetchone()
    conn.close()
    return {
        "name": row[0], "goal": row[1], "skills": row[2],
        "experience": row[3], "target_role": row[4],
        "city": row[5], "university": row[6]
    }

def save_message(role, content):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO chat_history (role, content) VALUES (?, ?)", (role, content))
    conn.commit()
    conn.close()

def get_recent_history(limit=12):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role, content FROM chat_history ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

def get_cached_tip():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today = str(date.today())
    c.execute("SELECT tip_date, tip_text FROM tip_cache WHERE id=1")
    row = c.fetchone()
    conn.close()
    if row and row[0] == today and row[1]:
        return row[1]
    return None

def set_cached_tip(tip_text):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today = str(date.today())
    c.execute("UPDATE tip_cache SET tip_date=?, tip_text=? WHERE id=1", (today, tip_text))
    conn.commit()
    conn.close()

# ─── PROGRESS ───────────────────────────────────────────
def save_progress(jobs_applied, study_hours, mood=3, note=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today = str(date.today())
    c.execute("DELETE FROM progress_logs WHERE log_date=?", (today,))
    c.execute("INSERT INTO progress_logs VALUES (NULL, ?, ?, ?, ?, ?)",
              (today, jobs_applied, study_hours, mood, note))
    conn.commit()
    conn.close()

def get_today_progress():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today = str(date.today())
    c.execute("SELECT jobs_applied, study_hours, mood, note FROM progress_logs WHERE log_date=?", (today,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"jobs_applied": row[0], "study_hours": row[1], "mood": row[2], "note": row[3]}
    return {"jobs_applied": 0, "study_hours": 0, "mood": 3, "note": ""}

def get_weekly_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT SUM(jobs_applied), SUM(study_hours), COUNT(*)
        FROM progress_logs
        WHERE log_date >= date('now', '-7 days')
    """)
    row = c.fetchone()
    conn.close()
    return {
        "jobs_this_week": row[0] or 0,
        "study_hours_this_week": row[1] or 0,
        "active_days": row[2] or 0
    }

# ─── MODELS ─────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    mode: str = "chat"

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    goal: Optional[str] = None
    skills: Optional[str] = None
    experience: Optional[str] = None
    target_role: Optional[str] = None
    city: Optional[str] = None
    university: Optional[str] = None

class ProgressUpdate(BaseModel):
    jobs_applied: int = 0
    study_hours: float = 0
    mood: int = 3
    note: str = ""

class PlanRequest(BaseModel):
    focus: str = "balanced"
    hours_available: int = 8

# ─── GEMINI ─────────────────────────────────────────────
async def call_gemini(system: str, messages: list) -> str:
    contents = []
    for m in messages:
        role = "model" if m["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})

    # Gemini needs alternating turns starting with user
    if contents and contents[0]["role"] == "model":
        contents.insert(0, {"role": "user", "parts": [{"text": "Hi"}]})

    # Merge consecutive same-role messages (Gemini strict alternation)
    merged = []
    for msg in contents:
        if merged and merged[-1]["role"] == msg["role"]:
            merged[-1]["parts"][0]["text"] += "\n\n" + msg["parts"][0]["text"]
        else:
            merged.append(msg)

    if not merged or merged[-1]["role"] != "user":
        raise HTTPException(400, "Last message must be from user")

    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": merged,
        "generationConfig": {
            "temperature": 0.85,
            "maxOutputTokens": 1024,
        }
    }

    async with httpx.AsyncClient(timeout=30) as client:
        for model in GEMINI_MODELS:
            try:
                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{model}:generateContent?key={GEMINI_KEY}"
                )
                r = await client.post(url, json=payload)

                if r.status_code == 200:
                    data = r.json()
                    try:
                        return data["candidates"][0]["content"]["parts"][0]["text"]
                    except (KeyError, IndexError):
                        return "I'm here, Divya! Could you rephrase that? I want to make sure I help you properly. 💙"

                elif r.status_code == 400:
                    err = r.json().get("error", {}).get("message", "Bad request")
                    raise HTTPException(400, f"Gemini error: {err}")

                # 429 = rate limit, 503 = overload — try next model
            except HTTPException:
                raise
            except Exception:
                continue

    raise HTTPException(500, "All Gemini models failed. Check GEMINI_API_KEY on Render.")

def build_system(mode: str = "chat") -> str:
    return SYSTEM_PROMPT.format(mode=mode)

# ─── ROUTES ─────────────────────────────────────────────
@app.on_event("startup")
def startup():
    init_db()

@app.get("/health")
def health():
    return {"status": "ok", "gemini_key_set": bool(GEMINI_KEY)}

@app.get("/api/profile")
def get_profile_route():
    return get_profile()

@app.post("/api/profile")
def update_profile(data: ProfileUpdate):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    fields = {k: v for k, v in data.dict().items() if v is not None}
    if fields:
        set_clause = ", ".join(f"{k}=?" for k in fields)
        c.execute(f"UPDATE user_profile SET {set_clause} WHERE id=1", list(fields.values()))
        conn.commit()
    conn.close()
    return get_profile()

@app.post("/api/chat")
async def chat(req: ChatRequest):
    progress = get_today_progress()
    history = get_recent_history()

    user_msg = (
        f"[Today's progress — Jobs applied: {progress['jobs_applied']}, "
        f"Study hours: {progress['study_hours']}, Mood: {progress['mood']}/5]\n\n"
        f"{req.message}"
    )

    messages = history + [{"role": "user", "content": user_msg}]
    system = build_system(req.mode)
    reply = await call_gemini(system, messages)

    save_message("user", req.message)
    save_message("assistant", reply)

    return {"reply": reply}

@app.post("/api/progress")
def update_progress(data: ProgressUpdate):
    save_progress(data.jobs_applied, data.study_hours, data.mood, data.note)
    return {**get_today_progress(), **get_weekly_stats()}

@app.get("/api/progress/today")
def progress_today():
    return {**get_today_progress(), **get_weekly_stats()}

@app.get("/api/tips/daily")
async def tip():
    # Cache tip — only 1 Gemini call per day for tips
    cached = get_cached_tip()
    if cached:
        return {"tip": cached}

    prompt = (
        "Give Divya exactly 1 short, specific, encouraging tip for today (2-3 sentences max). "
        "Make it relevant to finding a Werkstudent Data Analyst job in Germany or improving her SQL/Excel skills. "
        "Be warm and personal, not generic."
    )
    system = build_system()
    result = await call_gemini(system, [{"role": "user", "content": prompt}])
    set_cached_tip(result)
    return {"tip": result}

@app.post("/api/plan/generate")
async def generate_plan(req: PlanRequest):
    profile = get_profile()
    prompt = f"""
Create a structured daily plan for Divya. Return ONLY valid JSON — no markdown, no explanation.

Focus: {req.focus}
Hours available today: {req.hours_available}
Her goal: {profile['goal']}
Her skills: {profile['skills']}
Her background: {profile['experience']}

JSON format exactly:
{{
  "greeting": "warm personal line for Divya",
  "top_priority": "the single most important task today",
  "blocks": [
    {{
      "time": "9:00 AM",
      "category": "Study",
      "task": "specific task description",
      "tip": "short practical tip"
    }}
  ],
  "end_of_day_check": "evening reflection question for her"
}}

Rules:
- Categories: Study, Career, Break, Job, Wellbeing, Personal
- Create {min(req.hours_available, 8)} time blocks
- Job blocks should mention specific platforms like LinkedIn, StepStone, Indeed.de
- Study blocks should mention free resources like Coursera, W3Schools, YouTube
- Make it realistic and encouraging
""".strip()

    system = build_system("planner")
    raw = await call_gemini(system, [{"role": "user", "content": prompt}])

    clean = raw.strip()
    if clean.startswith("```"):
        parts = clean.split("```")
        clean = parts[1] if len(parts) > 1 else clean
        if clean.startswith("json"):
            clean = clean[4:]
        clean = clean.strip()

    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        return {"raw": raw, "error": True}

@app.get("/api/roadmap")
async def roadmap():
    prompt = """
Give Divya a clear 12-week roadmap to become a job-ready Data Analyst in Germany.
Return ONLY valid JSON — no markdown.

Format:
{
  "weeks": [
    {
      "week": "Week 1-2",
      "theme": "short theme title",
      "tasks": ["task 1", "task 2", "task 3"],
      "goal": "what she achieves by end of this phase"
    }
  ],
  "key_platforms": ["platform 1", "platform 2"],
  "quick_wins": ["thing she can do today 1", "thing she can do today 2"]
}

Make it realistic for someone with her background (2.5 years IT support, basic SQL, intermediate Excel).
Focus on Werkstudent roles during Master's in Germany.
""".strip()

    system = build_system("career")
    raw = await call_gemini(system, [{"role": "user", "content": prompt}])

    clean = raw.strip()
    if clean.startswith("```"):
        parts = clean.split("```")
        clean = parts[1] if len(parts) > 1 else clean
        if clean.startswith("json"):
            clean = clean[4:]
        clean = clean.strip()

    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        return {"raw": raw}

# ─── STATIC FRONTEND ────────────────────────────────────
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    @app.get("/")
    def serve_frontend():
        return FileResponse(os.path.join(frontend_path, "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
