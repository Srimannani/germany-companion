# 🌟 Mia — Germany Companion App

An AI-powered companion for Master's students in Germany.
Chat • Daily Planner • Career Coach • Study Assistant

---

## 📁 Folder Structure

```
germany-companion/
│
├── backend/
│   ├── main.py           ← FastAPI server (ALL backend logic)
│   ├── requirements.txt  ← Python dependencies
│   ├── .env              ← API key (never commit this!)
│   └── companion.db      ← SQLite database (auto-created)
│
├── frontend/
│   └── index.html        ← Complete single-page frontend
│
├── Procfile              ← For Render deployment
└── README.md
```

---

## ⚙️ Setup (Local)

### Step 1 — Install Python dependencies

```bash
cd backend
pip install -r requirements.txt
```

### Step 2 — Add your Claude API key

Edit `backend/.env`:
```
CLAUDE_API_KEY=sk-ant-...your-key-here...
```

Or set it as an environment variable:
```bash
export CLAUDE_API_KEY=sk-ant-...
```

Get your key at: https://console.anthropic.com/

### Step 3 — Run the server

```bash
cd backend
python main.py
```

Server starts at: http://localhost:8000

### Step 4 — Open the app

Open your browser: **http://localhost:8000**

---

## 🔌 Plug in Your System Prompt

Open `backend/main.py` and find the `SYSTEM_PROMPT` variable (around line 30).
Replace the entire string with your custom system prompt.

Keep these placeholders — they get filled with profile data automatically:
- `{name}` → user's name
- `{goal}` → user's goal

---

## 🚀 Deploy for Free (Render)

1. Push this folder to GitHub
2. Go to https://render.com → New → Web Service
3. Connect your GitHub repo
4. Set:
   - **Build Command:** `pip install -r backend/requirements.txt`
   - **Start Command:** `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add Environment Variable: `CLAUDE_API_KEY` = your key
6. Deploy! You'll get a free `.onrender.com` URL

---

## 🧩 API Endpoints

| Method | Endpoint              | Purpose                        |
|--------|-----------------------|--------------------------------|
| GET    | /api/profile          | Get user profile               |
| POST   | /api/profile          | Update name/goal               |
| POST   | /api/chat             | Send chat message              |
| POST   | /api/plan/generate    | Generate daily plan            |
| GET    | /api/plan/today       | Get today's saved plan         |
| GET    | /api/tips/daily       | Get one daily tip              |
| GET    | /api/history          | Get recent chat history        |
| DELETE | /api/history          | Clear chat history             |

---

## 💡 Features

- **Chat** — General, Study, Career, Planner modes
- **Daily Planner** — AI-generated schedules with time blocks
- **Career Coach** — 6 quick-access career guidance cards
- **Profile Memory** — Saves name + goal in SQLite, used in every prompt
- **Daily Tip** — Personalized tip on sidebar

---

## 🔧 Customize

- Change the model in `main.py`: `CLAUDE_MODEL = "claude-..."` 
- Increase chat history depth: change `limit=10` in `get_recent_history()`
- Add more career cards in `frontend/index.html` — just copy a `.career-card` block
