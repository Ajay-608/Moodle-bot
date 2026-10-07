# MoodleBot

MoodleBot is a Django learning chatbot with account roles, course-document
retrieval, FAISS similarity search, and Groq/OpenRouter chat completions.

**Production architecture:** GitHub `main` → Render Web Service → Gunicorn →
Django → Render PostgreSQL. PostgreSQL is the source of truth; FAISS is a
rebuildable retrieval index derived from its Documents.

## Local development

Use Python 3.11. Copy `.env.example` to `.env`, provide a local-only
`SECRET_KEY`, set `DEBUG=True`, and leave `DATABASE_URL` blank to use the
ignored local SQLite database.

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py populate_sample_data
python manage.py runserver
```

`populate_sample_data` is local-development-only and refuses to run with
`DEBUG=False`. Public registration creates student accounts only; teacher and
administrator privileges remain under administrator control.

## Render deployment

Configure the existing Render Web Service to deploy `main` with Auto-Deploy.
Set its Build and Start Commands to:

**Build Command**

```text
pip install -r requirements.txt && python manage.py migrate --noinput && python manage.py collectstatic --noinput && python manage.py initialize_production
```

**Start Command**

```text
gunicorn --bind 0.0.0.0:$PORT --timeout 180 moodlebot.wsgi:application
```

Set these required environment variables in Render:

- `SECRET_KEY`: a newly generated secret
- `DEBUG=False`
- `DATABASE_URL`: the fresh Render PostgreSQL connection URL
- `ALLOWED_HOSTS`: the actual Render hostname, without the scheme
- `CSRF_TRUSTED_ORIGINS`: the actual HTTPS origin, including `https://`
- `PYTHON_VERSION=3.11.9`
- `GROQ_API_KEY` and/or `OPENROUTER_API_KEY` for hosted LLM responses

Optional model configuration uses `LLM_MODEL` and `OPENROUTER_MODEL`. Optional
`CORS_ALLOWED_ORIGINS` is only needed for a separate cross-origin client.
`FAISS_INDEX_PATH` overrides the generated-index path. Its local default is
`<project directory>/rag_index.faiss`.

The optional deployment administrator is configured with all three variables
`DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, and
`DJANGO_SUPERUSER_PASSWORD`. Leave all three unset to skip automatic admin
creation. Passwords are never printed. An existing configured account is
preserved and is made a staff superuser without resetting its password.

`initialize_production` runs during the Build Command. It checks the database,
optionally creates the deployment administrator, initializes the knowledge
base only when there are no Documents, and ensures a valid FAISS index exists.
It is safe to run again. No Render Shell or manual FAISS upload is needed.
Production begins with a fresh PostgreSQL database: SQLite users, chats,
messages, Documents, IDs, and old FAISS data are not migrated or reused.

The course text files in `media/*.txt` initialize fresh PostgreSQL Documents.
`all-MiniLM-L6-v2` creates normalized 384-dimensional vectors associated with
those current PostgreSQL `Document.id` values. The builder verifies index
dimensions, counts, IDs, and a content fingerprint, then writes atomically.
A valid index is reused.

Render Free filesystem contents are not guaranteed to persist across deploys
or instance restarts. PostgreSQL remains authoritative, and the index can be
rebuilt from its Documents. If it is missing or stale at runtime, the first
request requiring RAG rebuilds it under a cross-process file lock; normal
requests reuse the in-memory index and model within each Gunicorn worker.
The current Gunicorn command uses its default single worker to limit memory
use. A runtime rebuild can take time and memory on a Free instance; the chat
endpoint reports a controlled temporary-unavailability response if a rebuild
fails rather than treating retrieval as successful.

Django serves collected static files through WhiteNoise. Render supplies
`$PORT`; no fixed port or Nginx configuration is used.

For detailed environment and deployment notes, see
[QUICK_START.md](./QUICK_START.md) and
[the PostgreSQL initialization runbook](./docs/fresh-postgresql-initialization.md).
