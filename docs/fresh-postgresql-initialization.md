# Render deployment and fresh PostgreSQL initialization

## Architecture and data policy

```text
GitHub main
  -> Render Web Service
  -> Gunicorn
  -> Django
  -> fresh Render PostgreSQL
```

PostgreSQL is the source of truth for application and knowledge-base data.
FAISS is a derived, rebuildable index. Production starts with a fresh database:
do not import SQLite fixtures or reuse SQLite users, profiles, chats, messages,
Documents, IDs, or a previous FAISS index. The committed `media/*.txt` files
are the source for fresh Documents.

## Render service configuration

Configure the existing Render Web Service to deploy `main` with Auto-Deploy.
Set `PYTHON_VERSION=3.11.9`.

**Build Command**

```text
pip install -r requirements.txt && python manage.py migrate --noinput && python manage.py collectstatic --noinput && python manage.py initialize_production
```

**Start Command**

```text
gunicorn --bind 0.0.0.0:$PORT --timeout 180 moodlebot.wsgi:application
```

The Start Command uses Render's assigned port and Gunicorn's default single
worker. Static output is served by WhiteNoise from `STATIC_ROOT`. Nginx is not
required. There is no dedicated application health endpoint; use Render's
default TCP health check.

### Environment variables

Configure these values privately in Render:

| Name | Requirement |
|---|---|
| `SECRET_KEY` | Required; generate a unique secret |
| `DEBUG` | Required; set to `False` |
| `DATABASE_URL` | Required; URL for the fresh Render PostgreSQL database |
| `ALLOWED_HOSTS` | Required; actual Render hostname, no scheme |
| `CSRF_TRUSTED_ORIGINS` | Required; actual HTTPS origin, including `https://` |
| `PYTHON_VERSION` | Set to `3.11.9` |
| `GROQ_API_KEY` | Optional provider key |
| `OPENROUTER_API_KEY` | Optional provider key/fallback |
| `LLM_MODEL` | Optional; defaults to `llama-3.1-8b-instant` |
| `OPENROUTER_MODEL` | Optional; defaults to `meta-llama/llama-3.1-8b-instruct:free` |
| `CORS_ALLOWED_ORIGINS` | Optional; only for a separate cross-origin client |
| `FAISS_INDEX_PATH` | Optional; defaults to `<project directory>/rag_index.faiss` |

At least one LLM provider key is needed for hosted model responses. For
automatic deployment-admin creation, set all of
`DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, and
`DJANGO_SUPERUSER_PASSWORD`. All three are optional as a group. The configured
password is never printed; an existing username is preserved and promoted to
staff/superuser without resetting its password.

`.env.example` contains example/empty values only. Never commit `.env`,
database URLs, API keys, or administrator passwords.

## Automatic initialization

The Build Command applies migrations, collects static files, then invokes
`python manage.py initialize_production`. The management command:

1. Verifies database connectivity and requires PostgreSQL when `DEBUG=False`.
2. Optionally creates or verifies the configured deployment administrator.
3. Initializes the knowledge base only when no Documents exist. Existing
   Documents are left untouched.
4. Ensures a current, valid FAISS index exists.

No Render Shell or separate manual `build_index.py` invocation is required.
Repeated invocation is safe. Routine web requests do not rerun migrations or
knowledge-base initialization.

`initialize_knowledge_base` loads committed course text files in deterministic
filename order, normalizes whitespace, creates 500-character chunks in an
atomic transaction, and lets PostgreSQL assign fresh IDs. It refuses to
replace existing Documents.

## FAISS generation and runtime recovery

`build_index.py`, `initialize_production`, and `rag_engine.py` use the single
`settings.FAISS_INDEX_PATH` setting. The local default is
`<project directory>/rag_index.faiss`; set `FAISS_INDEX_PATH` to override it.
The generated FAISS file and lock/temp files are ignored by Git.

The builder uses `all-MiniLM-L6-v2` to create normalized 384-dimensional
vectors for current database Documents and associates each vector with its
PostgreSQL `Document.id`. It validates dimensions, finite vector values,
vector count, unique IDs, the exact Document ID set, and a content fingerprint
before atomically replacing the generated index and metadata. Changes to
Document IDs or content invalidate the index. A valid index is reused; a
missing, corrupt, incompatible, or stale index is rebuilt.

Render Free does not guarantee filesystem persistence across deploys or
instance restarts. The PostgreSQL Documents remain authoritative. If the index
is missing or stale at runtime, the first request requiring RAG rebuilds it
from PostgreSQL under a cross-process filesystem lock. Concurrent Gunicorn
workers therefore do not each initiate an independent build. The index and
embedding model are cached in each worker process after use; the current
Gunicorn command uses one worker to limit memory consumption. If rebuilding
fails, the request returns a controlled temporary-unavailability response
and logs the actual exception; it does not claim retrieval succeeded.

The runtime fallback can incur model-load/build latency and memory use on a
Free instance. The Build Command proactively creates the index, but runtime
recovery remains necessary because the Free filesystem is ephemeral. No paid
persistent disk or manual file upload is required.

## Local development

Local development can use SQLite when `DEBUG=True` and `DATABASE_URL` is
unset. Use `python manage.py migrate` and `python manage.py runserver`
normally. Do not run production initialization automatically on server
startup. Production configuration rejects missing or non-PostgreSQL
`DATABASE_URL` values when `DEBUG=False`.

Legacy SQLite fixture scripts are optional local audit tools only. They are
not part of deployment or production initialization; no SQLite data migration
is part of this architecture.
