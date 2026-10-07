# MoodleBot - AI-Powered Educational Chatbot

**Status:** AWS deployment preparation only (not deployed) | **Django:** 4.2.7 | **Database:** SQLite locally; fresh Amazon RDS PostgreSQL planned via `DATABASE_URL` | **Python:** 3.11 | **AI:** Groq with OpenRouter fallback

---

## 🤖 What is MoodleBot?

MoodleBot is an AI-powered educational chatbot for students, teachers, and admins built on Django. It uses Retrieval-Augmented Generation (RAG) to answer student questions from course materials.

### How it works:
1. Student asks a question in the chat
2. Sentence Transformer converts the question into a vector
3. FAISS searches 2000+ course document chunks for the most relevant content
4. Groq generates a conversational answer, with OpenRouter as a fallback
5. Student sees a clean, tutor-style explanation with confidence score

---

## 🚀 Quick Start

### Prerequisites

Install dependencies with `python -m pip install -r requirements.txt`.
For local development, copy `.env.example` to `.env`, set a fresh local
`SECRET_KEY`, set `DEBUG=True`, and leave `DATABASE_URL` blank for SQLite.

### Run the Project

```bash
# Local development database
python manage.py migrate
python manage.py populate_sample_data
python manage.py runserver
```

**Access:** http://localhost:8000

---

`populate_sample_data` is local-development-only and refuses to run with
`DEBUG=False`. It preserves existing passwords, roles, and application data.

---

## 📁 Project Structure

```
moodlebot_project/
├── core/
│   ├── models.py              # UserProfile, ResponseFeedback, LearningGap, TAMSurvey
│   ├── views.py               # Role-based dashboard routing
│   └── management/commands/
│       └── populate_sample_data.py
├── chat/
│   ├── models.py              # ChatSession, Message
│   ├── views.py               # send_message() with RAG integration
│   └── urls.py
├── knowledge/
│   ├── models.py              # Document (chunks from course materials)
│   └── views.py               # Upload and FAQ views
├── admin_panel/
│   └── views.py               # Teacher/Admin analytics
├── analytics/
│   └── views.py               # Teacher dashboard stats
├── rag/                       # RAG app registration
├── templates/
│   └── core/
│       ├── student_dashboard.html
│       ├── teacher_dashboard.html
│       └── admin_dashboard.html
├── moodlebot/
│   ├── settings.py            # Django config
│   ├── urls.py                # Root URL routing
│   └── wsgi.py
├── rag_engine.py              # Core AI engine (FAISS + Groq/OpenRouter)
├── build_index.py             # Builds PostgreSQL-backed ID-mapped FAISS index
├── index_text_files.py        # Legacy destructive local SQLite loader
├── database_dataset.json      # Alternate curated Q&A corpus
├── populate_sample_data.py    # Creates test users and sample data
├── database_dataset.json      # 140 pre-written DBMS Q&A topics
├── requirements.txt
└── manage.py
```

---

## 🤖 RAG Engine

**File:** `rag_engine.py`

- **Embedding model:** `all-MiniLM-L6-v2` (384-dim vectors, runs locally)
- **Vector search:** FAISS ID-mapped index — retrieves chunks by their Django Document IDs
- **Language model:** Groq, with OpenRouter fallback
- **Fallback:** Safe plain-text response if both providers are unavailable
- **Confidence score:** 88% average

**Flow:**
```
Question → Sentence Transformer → FAISS Search → Top 3 Chunks → Groq/OpenRouter → Answer
```

---

## 📊 Dashboard Architecture

### Student Dashboard (`/`)
- Chat interface with conversation history
- Learning gap tracking
- Feedback system (thumbs up/down)
- Bot accuracy percentage

### Teacher Dashboard (`/admin-panel/`)
- Active students monitoring
- Top questions asked by students
- Struggling students list
- Low-rated responses review

### Admin Dashboard (`/admin-panel/`)
- User management (student/teacher/admin roles)
- System-wide usage statistics
- Knowledge base document count
- TAM Survey results

---

## 🗄️ Database Schema

```python
UserProfile     # user_type: student/teacher/admin
ChatSession     # user conversations
Message         # individual messages with confidence_score
ResponseFeedback # 1-5 star ratings with comments
LearningGap     # tracked weak topics per student
TAMSurvey       # Technology Acceptance Model responses
Document        # course material chunks (indexed in FAISS)
```

---

## 🔌 API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/` | GET | Role-based dashboard |
| `/chat/` | GET | Chat interface |
| `/chat/send/` | POST | Send message to bot |
| `/admin-panel/` | GET | Teacher/Admin analytics |
| `/knowledge/upload/` | POST | Upload course material |
| `/register/` | POST | User registration |
| `/login/` | GET/POST | Authentication |

---

## ⚙️ Configuration

### Environment Variables

Copy `.env.example` to `.env` for local development. `SECRET_KEY` is required.
If `DEBUG=True` and `DATABASE_URL` is absent, the project uses local SQLite.
Production requires `DATABASE_URL` to contain the Amazon RDS PostgreSQL
connection string in the EC2 application environment. Never commit real
credentials.

```
SECRET_KEY=<local random secret>
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=
```

Production is planned to start with a fresh Amazon RDS PostgreSQL database.
SQLite data is not migrated: old users, profiles, chats/messages, Documents,
feedback, learning gaps, surveys, and IDs are not carried over. Create a new
PostgreSQL superuser; users register normally after launch. The fresh database
gets new Document IDs and a newly generated FAISS index; the old
`rag_index.faiss` is not reused.

The one-time production initialization order is:

```powershell
# Securely configure DATABASE_URL, SECRET_KEY, ALLOWED_HOSTS,
# CSRF_TRUSTED_ORIGINS, DEBUG=False, and required provider secrets
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py initialize_knowledge_base
python build_index.py
python manage.py check
python manage.py test
python manage.py collectstatic --noinput
```

`initialize_knowledge_base` is for an empty knowledge database and refuses to
run if Documents already exist. Run `build_index.py` after it. Do not run
`populate_sample_data` or destructive/legacy content loaders in production.
SQLite remains an optional local-development fallback; RDS is required for
durable production persistence. Follow the
[fresh PostgreSQL and AWS runbook](docs/fresh-postgresql-initialization.md).
AWS provisioning is not complete: RDS, EC2, DNS, HTTPS, and deployment do not
exist or have been tested yet.

---

## 📈 Performance

- **Chat response time:** Depends on model loading, retrieval, and AI provider response
- **RAG retrieval:** O(log n) with FAISS
- **Knowledge base:** Chunks generated from the committed course text files
- **Bot accuracy:** 88%
- **Concurrent users:** ~10-20 on local machine

---

## 🐛 Known Limitations

- ❌ No real-time teacher chat intervention
- ❌ CSV export not yet implemented
- ❌ Quiz generation pending
- ❌ Concept mapping UI pending
- ⚠️ Response time slower on machines without GPU (5-15 seconds)

---

## 🚀 Phase 2 Roadmap

- [ ] Production AWS deployment and HTTPS configuration
- [ ] Quiz generation from course materials
- [ ] Real-time teacher intervention
- [ ] CSV analytics export
- [ ] Student progress badges
- [ ] Email notifications for teachers
- [ ] Mobile app (React Native)

---

## 📞 Contact

**Author:** Ajay  
**Repository:** https://github.com/Ajay-608/Moodle-bot  
**License:** MIT  
**Last Updated:** June 2026  
**Version:** 2.0 - Ollama RAG