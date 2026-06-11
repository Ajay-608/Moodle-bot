## MoodleBot - Quick Start Guide
# Running on a New Laptop

================================================================
STEP 1 - INSTALL PYTHON
================================================================
Download Python 3.11 from https://www.python.org/downloads/
During install - CHECK "Add Python to PATH"
Verify: open terminal and run:
  python --version

================================================================
STEP 2 - CLONE THE PROJECT
================================================================
Open terminal and run:

  git clone https://github.com/Ajay-608/Moodle-bot.git
  cd Moodle-bot

================================================================
STEP 3 - CREATE VIRTUAL ENVIRONMENT
================================================================
  python -m venv venv

Activate it:
  Windows : venv\Scripts\activate.bat
  Mac/Linux: source venv/bin/activate

You should see (venv) at the start of your terminal line.

================================================================
STEP 4 - INSTALL PYTHON PACKAGES
================================================================
  pip install -r requirements.txt

This installs Django, FAISS, Sentence Transformers, etc.
Takes 5-10 minutes first time.

================================================================
STEP 5 - INSTALL OLLAMA (LOCAL AI)
================================================================
Go to: https://ollama.com/download
Download and install for your operating system.

Then download the AI model (1.3GB - one time only):
  ollama pull llama3.2:1b

Wait for download to complete (5-10 minutes).

Windows: Ollama starts automatically in background after install.
Mac/Linux: Run this in a separate terminal before step 9:
  ollama serve

================================================================
STEP 6 - CREATE .env FILE
================================================================
In your project folder, create a file called .env
Add this content:

  SECRET_KEY=moodlebot-secret-key-2024-xkq92plwm83
  DEBUG=True
  ALLOWED_HOSTS=localhost,127.0.0.1

No API key needed - MoodleBot runs locally!

================================================================
STEP 7 - SET UP DATABASE
================================================================
  python manage.py migrate

================================================================
STEP 8 - CREATE TEST USERS
================================================================
  python manage.py populate_sample_data

This creates:
  - 1 Admin account
  - 2 Teacher accounts
  - 5 Student accounts
  - Sample chat sessions and data

================================================================
STEP 9 - ADD COURSE CONTENT
================================================================
Option A - Use text files (recommended):
  Put your .txt course files in the media/ folder
  Then run:
    python index_text_files.py

Option B - Use built-in dataset (140 DBMS topics):
  python load_database_dataset.py

================================================================
STEP 10 - BUILD AI SEARCH INDEX
================================================================
  python build_index.py

This converts all course content into vectors for AI search.
Takes 2-5 minutes depending on content size.

================================================================
STEP 11 - START THE SERVER
================================================================
  python manage.py runserver

Open browser and go to: http://localhost:8000

================================================================
LOGIN CREDENTIALS
================================================================
Role     Username         Password
------   ---------------  ----------
Admin    admin            admin123
Teacher  prof_smith       teacher123
Student  alice_student    student123

================================================================
EVERY TIME YOU WANT TO RUN THE PROJECT
================================================================
1. Open terminal
2. Navigate to project folder:
   cd path/to/Moodle-bot
3. Activate venv:
   venv\Scripts\activate.bat   (Windows)
   source venv/bin/activate    (Mac/Linux)
4. Start server:
   python manage.py runserver
5. Open: http://localhost:8000

Note: Ollama starts automatically on Windows.
On Mac/Linux run "ollama serve" in a separate terminal first.

================================================================
TROUBLESHOOTING
================================================================

Problem : "RAG unavailable: numpy dtype size changed"
Fix     : pip install numpy==1.26.4

Problem : "RAG unavailable: cannot import cached_download"
Fix     : pip install sentence-transformers==2.7.0

Problem : "RAG unavailable: huggingface-hub version"
Fix     : pip install huggingface_hub==0.36.2

Problem : Bot gives fallback answers only
Fix     : Make sure Ollama is running
          Windows: check system tray for Ollama icon
          Mac/Linux: run "ollama serve" in separate terminal

Problem : "Created empty FAISS index" on startup
Fix     : Run python build_index.py then restart server

Problem : Port already in use
Fix     : python manage.py runserver 8001
          Then open http://localhost:8001

================================================================
SYSTEM REQUIREMENTS
================================================================
OS      : Windows 10/11, macOS, Linux
Python  : 3.10 or 3.11
RAM     : Minimum 8GB (16GB recommended)
Storage : 5GB free space (for AI model)
Internet: Only needed for first-time package installation

================================================================