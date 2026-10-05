# MoodleBot — Quick Start Guide

**Live app:** https://moodle-bot-1zx9.onrender.com
**Repo:** https://github.com/Ajay-608/Moodle-bot

---

## 1. Local Setup (run it on your own machine)

### Prerequisites
- Python 3.11 (must match — newer versions break `faiss-cpu`)
- Git

### Steps

```bash
# 1. Clone the repo
git clone https://github.com/Ajay-608/Moodle-bot.git
cd Moodle-bot

# 2. Install dependencies
python -m pip install -r requirements.txt

# 3. Create your local .env file (see section 2 below for what goes in it)

# 4. Run database migrations
python manage.py migrate

# 5. Populate sample users, courses, and demo data
python manage.py populate_sample_data

# 6. Index course text files into the database
python index_text_files.py

# 7. Build the FAISS vector search index
python build_index.py

# 8. Start the local server
python manage.py runserver
```

Visit `http://localhost:8000` and log in with one of the demo accounts below.

---

## 2. Environment Variables (`.env` file)

Create a `.env` file in the project root with:

```
SECRET_KEY=your-local-dev-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

GROQ_API_KEY=your-groq-key
LLM_MODEL=openai/gpt-oss-20b

OPENROUTER_API_KEY=your-openrouter-key
OPENROUTER_MODEL=openrouter/free
```

- Get a free Groq key: https://console.groq.com
- Get a free OpenRouter key: https://openrouter.ai/keys
- **Never commit this file** — it's already in `.gitignore`

---

## 3. Default Demo Credentials

| Role | Username | Password |
|---|---|---|
| Admin | `admin` | `admin123` |
| Teacher | `prof_smith` | `teacher123` |
| Student | `alice_student` | `student123` |

⚠️ These are public in this repo — change them before using this for anything beyond a demo.

---

## 4. How the Chatbot Works

1. User asks a question in the chat UI
2. `rag_engine.search()` embeds the question (Sentence-Transformers) and finds the most relevant course content chunks (FAISS)
3. `rag_engine.generate_response()` sends those chunks + the question to **Groq** (primary LLM)
4. If Groq fails (rate limit, outage, bad key), it automatically retries with **OpenRouter** (fallback)
5. If both fail, it returns a safe plain-text fallback response — the app never hard-crashes on a chat request

---

## 5. Deploying Your Own Copy (Render)

1. Fork/clone the repo, push to your own GitHub
2. Create a free account at render.com, connect your GitHub
3. **New → Web Service**, select your repo
4. **Build Command:**
   ```
   pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate && python manage.py populate_sample_data && python index_text_files.py && python build_index.py
   ```
5. **Start Command:**
   ```
   gunicorn moodlebot.wsgi:application --bind 0.0.0.0:$PORT --timeout 120 --workers 1
   ```
6. **Environment Variables** (Render dashboard → Environment tab):
   ```
   SECRET_KEY=<generate a fresh one>
   DEBUG=False
   ALLOWED_HOSTS=<your-app-name>.onrender.com,localhost,127.0.0.1
   PYTHON_VERSION=3.11.9
   GROQ_API_KEY=<your key>
   LLM_MODEL=openai/gpt-oss-20b
   OPENROUTER_API_KEY=<your key>
   OPENROUTER_MODEL=openrouter/free
   ```
7. Deploy. Once live, copy the assigned URL and update `ALLOWED_HOSTS` to match it exactly, then save (triggers a redeploy).

**Generate a fresh `SECRET_KEY` with:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

---

## 6. Keeping It Awake (Free Tier Only)

Render's free tier sleeps after ~15 minutes of inactivity, causing a 30–90 second delay on the next visit. To prevent this:

1. Sign up at uptimerobot.com (free)
2. Add a new **HTTP(s) monitor** pointing to your live URL
3. Set check interval to **5 minutes**
4. Save — your app will now stay awake continuously

---

## 7. Common Issues & Fixes

| Symptom | Cause | Fix |
|---|---|---|
| `faiss-cpu` install fails | Wrong Python version | Set `PYTHON_VERSION=3.11.9` env var |
| Build pulls huge CUDA packages | Default torch install | Already fixed via `--extra-index-url` CPU pin in `requirements.txt` |
| `CSRF verification failed` | Missing trusted origins | Already fixed via `CSRF_TRUSTED_ORIGINS` in `settings.py` |
| Chat returns `"Based on {source}: {query}"` | Both Groq and OpenRouter failed | Check API keys are valid and current in environment variables |
| `401 Unauthorized` from Groq | Revoked/rotated key not updated | Update `GROQ_API_KEY` in Render's Environment tab |
| Worker timeout on startup | Model loading takes >30s (gunicorn default) | Already fixed via `--timeout 120` in start command |
| `Bad Request (400)` on live site | Domain not in `ALLOWED_HOSTS` | Add the exact live domain to `ALLOWED_HOSTS` env var |

---

## 8. Tech Stack Summary

- **Backend:** Django 4.2.7, Django REST Framework
- **RAG pipeline:** Sentence-Transformers (`all-MiniLM-L6-v2`) + FAISS
- **LLM:** Groq (primary) + OpenRouter (fallback)
- **Hosting:** Render (free tier) + UptimeRobot keep-alive
- **Database:** SQLite