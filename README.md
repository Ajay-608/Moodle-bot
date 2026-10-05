# MoodleBot - AI-Powered Educational Chatbot

**Status:** ✅ Deployed | **Django Version:** 4.2.7 | **Database:** SQLite | **Python:** 3.11 | **AI:** Groq + OpenRouter | **RAG:** FAISS + Sentence Transformers

---

## 🤖 What is MoodleBot?

MoodleBot is an AI-powered educational chatbot designed for students, teachers, and administrators. It is built using the Django web framework and uses **Retrieval-Augmented Generation (RAG)** to answer questions using course-specific educational content.

The system retrieves relevant course material before generating an answer, helping keep responses grounded in the available knowledge base.

### How it works

1. Student asks a question in the chat
2. Sentence Transformer converts the question into a 384-dimensional embedding
3. FAISS searches the indexed course-document chunks
4. Relevant chunks are retrieved using vector similarity
5. MoodleBot checks whether relevant course information is available
6. The system uses the current chat session context when appropriate
7. Groq generates the final response
8. OpenRouter is used as a fallback if Groq is unavailable
9. The student receives a conversational answer with a retrieval confidence score

---

## 🌐 Live Demo

**Deployed Application:**

https://moodle-bot-1zx9.onrender.com

> Note: The application may take some time to start when using Render's free hosting tier.

---

## 🚀 Quick Start

### Prerequisites

```bash
# Python 3.11 recommended

# Clone the repository
git clone https://github.com/Ajay-608/Moodle-bot.git

cd Moodle-bot

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
**Version:** 2.0 - Ollama RAG
