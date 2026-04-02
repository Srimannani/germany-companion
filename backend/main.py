from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import sqlite3
import os
import json
import httpx
from datetime import date

app = FastAPI(title="Germany Companion API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── CONFIG ─────────────────────────────────────────────
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

GEMINI_MODELS = [
    "gemini-3.1-flash-lite-preview",  # try
    "gemini-2.5-flash",               # fallback
    "gemini-2.0-flash",               # fallback
]

DB_PATH = "companion.db"

# ─── SYSTEM PROMPT ──────────────────────────────────────
SYSTEM_PROMPT = """
You are Mia — an AI Companion + Study Assistant + Career Coach.

User:
- Name: {name}
- Goal: {goal}
- Skills: {skills}
- Experience: {experience}
- Target Role: {target_role}

Always:
1. Short support line
2. Clear guidance
3. 2–3 actionable steps

For career:
- Suggest roles
- Suggest platforms (LinkedIn, Indeed, StepStone)
- Give daily plan
- Give skill suggestion

Be practical. No generic advice.
"""

# ─── DATABASE ───────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS user_profile (
        id INTEGER PRIMARY KEY,
        name TEXT DEFAULT 'friend',
        goal TEXT DEFAULT 'get a Werkstudent job in Germany',
        skills TEXT DEFAULT 'SQL basics, Excel',
        experience TEXT DEFAULT '2.5 years Product Support Analyst (Infor IBMi)',
        target_role TEXT DEFAULT 'Data Analyst'
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT,
        content TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS progress_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        log_date TEXT,
        jobs_applied INTEGER,
        study_hours INTEGER
    )
    """)

    c.execute("INSERT OR IGNORE INTO user_profile (id) VALUES (1)")
    conn.commit()
    conn.close()

def get_profile():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, goal, skills, experience, target_role FROM user_profile WHERE id=1")
    row = c.fetchone()
    conn.close()

    return {
        "name": row[0],
        "goal": row[1],
        "skills": row[2],
        "experience": row[3],
        "target_role": row[4]
    }

def save_message(role, content):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO chat_history (role, content) VALUES (?, ?)", (role, content))
    conn.commit()
    conn.close()

def get_recent_history(limit=10):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role, content FROM chat_history ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

# ─── PROGRESS ───────────────────────────────────────────
def save_progress(jobs_applied, study_hours):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today = str(date.today())

    c.execute("DELETE FROM progress_logs WHERE log_date=?", (today,))
    c.execute("INSERT INTO progress_logs VALUES (NULL, ?, ?, ?)",
              (today, jobs_applied, study_hours))

    conn.commit()
    conn.close()

def get_today_progress():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today = str(date.today())

    c.execute("SELECT jobs_applied, study_hours FROM progress_logs WHERE log_date=?", (today,))
    row = c.fetchone()
    conn.close()

    if row:
        return {"jobs_applied": row[0], "study_hours": row[1]}
    return {"jobs_applied": 0, "study_hours": 0}

# ─── MODELS ─────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str

class ProgressUpdate(BaseModel):
    jobs_applied: int = 0
    study_hours: int = 0

# ─── GEMINI ─────────────────────────────────────────────
async def call_gemini(system, messages):
    contents = [{"role": "user", "parts": [{"text": system}]}]

    for m in messages:
        contents.append({
            "role": "user",
            "parts": [{"text": m["content"]}]
        })

    async with httpx.AsyncClient(timeout=30) as client:
        for model in GEMINI_MODELS:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}"

                r = await client.post(url, json={"contents": contents})

                if r.status_code == 200:
                    try:
                        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
                    except:
                        return "AI response error. Try again."

            except Exception:
                continue

    raise HTTPException(500, "Gemini failed")

def build_system(profile):
    return SYSTEM_PROMPT.format(**profile)

# ─── ROUTES ─────────────────────────────────────────────
@app.on_event("startup")
def startup():
    init_db()

@app.get("/api/profile")
def profile():
    return get_profile()

@app.post("/api/chat")
async def chat(req: ChatRequest):
    profile = get_profile()
    history = get_recent_history()
    progress = get_today_progress()

    user_msg = f"""
Progress:
Jobs applied: {progress['jobs_applied']}
Study hours: {progress['study_hours']}

Message:
{req.message}
"""

    messages = history + [{"role": "user", "content": user_msg}]
    system = build_system(profile)

    reply = await call_gemini(system, messages)

    save_message("user", req.message)
    save_message("assistant", reply)

    return {"reply": reply}

@app.post("/api/progress")
def update_progress(data: ProgressUpdate):
    save_progress(data.jobs_applied, data.study_hours)
    return get_today_progress()

@app.get("/api/progress/today")
def progress():
    return get_today_progress()

@app.get("/api/tips/daily")
async def tip():
    profile = get_profile()

    prompt = f"""
Give 1 practical tip for today.
Goal: {profile['goal']}
Role: {profile['target_role']}
Skills: {profile['skills']}
"""

    system = build_system(profile)
    result = await call_gemini(system, [{"role": "user", "content": prompt}])

    return {"tip": result}

# ─── STATIC ─────────────────────────────────────────────
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")

if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=os.path.join(frontend_path, "static")), name="static")

    @app.get("/")
    def home():
        return FileResponse(os.path.join(frontend_path, "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)
