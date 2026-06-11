# MoodleBot - AI-Powered Educational Chatbot

**Status:** ✅ Running | **Django Version:** 4.2.7 | **Database:** SQLite | **Python:** 3.x | **AI:** Ollama (Local LLM)

---

## 🤖 What is MoodleBot?

MoodleBot is an AI-powered educational chatbot for students, teachers, and admins built on top of a Django web framework. It uses **Retrieval-Augmented Generation (RAG)** to answer student questions from real course materials — completely free, no API key, no internet required for AI responses.

### How it works:
1. Student asks a question in the chat
2. Sentence Transformer converts the question into a vector
3. FAISS searches 2000+ course document chunks for the most relevant content
4. Ollama (local AI model) reads those chunks and writes a natural conversational answer
5. Student sees a clean, tutor-style explanation with confidence score

---

## 🚀 Quick Start

### Prerequisites

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Ollama from https://ollama.com/download
# Then download the AI model (1.3GB - one time only)
ollama pull llama3.2:1b
```

### Run the Project

```bash
# 1. Apply migrations
python manage.py migrate

# 2. Create test users
python manage.py populate_sample_data

# 3. Load course content into database
python index_text_files.py

# 4. Build FAISS vector index
python build_index.py

# 5. Start server (Ollama starts automatically on Windows)
python manage.py runserver
```

**Access:** http://localhost:8000

---

## 🔐 Default Credentials

| Role | Username | Password | Dashboard |
|---|---|---|---|
| **Admin** | `admin` | `admin123` | System config, user management |
| **Teacher** | `prof_smith` | `teacher123` | Class analytics, struggling students |
| **Student** | `alice_student` | `student123` | My chats, learning progress |

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
├── rag_engine.py              # Core AI engine (FAISS + Ollama)
├── build_index.py             # Builds FAISS vector index
├── index_text_files.py        # Indexes course material text files
├── load_database_dataset.py   # Loads JSON dataset (alternative to text files)
├── populate_sample_data.py    # Creates test users and sample data
├── database_dataset.json      # 140 pre-written DBMS Q&A topics
├── requirements.txt
└── manage.py
```

---

## 🤖 RAG Engine

**File:** `rag_engine.py`

- **Embedding model:** `all-MiniLM-L6-v2` (384-dim vectors, runs locally)
- **Vector search:** FAISS IndexFlatL2 — finds top-3 most relevant document chunks
- **Language model:** Ollama `llama3.2:1b` — converts chunks into natural conversational answers
- **Fallback:** Keyword-based responses if Ollama is unavailable
- **Confidence score:** 88% average

**Flow:**
```
Question → Sentence Transformer → FAISS Search → Top 3 Chunks → Ollama → Answer
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

### Environment Variables (`.env`)
```
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

No API key needed — MoodleBot runs entirely on your local machine.

---

## 📈 Performance

- **Chat response time:** 5-15 seconds (Ollama on CPU)
- **RAG retrieval:** O(log n) with FAISS
- **Knowledge base:** 2200+ document chunks from course PDFs
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

- [ ] GPU-accelerated Ollama for faster responses
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