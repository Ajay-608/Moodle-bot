# MoodleBot — Quick Start

**Production:** GitHub `main` → Render Web Service → Gunicorn → Django →
fresh Render PostgreSQL.

## Local development

Use Python 3.11. Copy `.env.example` to `.env`, set a local `SECRET_KEY`,
set `DEBUG=True`, and leave `DATABASE_URL` blank to use local SQLite.

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py populate_sample_data
python manage.py runserver
```

`populate_sample_data` is for local development only and refuses to run when
`DEBUG=False`.

## Render configuration

Configure the existing Render Web Service to deploy `main` with Auto-Deploy.
Set `PYTHON_VERSION=3.11.9` and these commands:

**Build Command**

```text
pip install -r requirements.txt && python manage.py migrate --noinput && python manage.py collectstatic --noinput && python manage.py initialize_production
```

**Start Command**

```text
gunicorn --bind 0.0.0.0:$PORT --timeout 180 moodlebot.wsgi:application
```

Set `SECRET_KEY`, `DEBUG=False`, `DATABASE_URL`, `ALLOWED_HOSTS`, and
`CSRF_TRUSTED_ORIGINS` in the Render environment. Use the actual hostname
without a scheme for `ALLOWED_HOSTS`, and its HTTPS origin for
`CSRF_TRUSTED_ORIGINS`. Configure `GROQ_API_KEY` and/or
`OPENROUTER_API_KEY` for hosted model responses. `LLM_MODEL`,
`OPENROUTER_MODEL`, `CORS_ALLOWED_ORIGINS`, and `FAISS_INDEX_PATH` are
optional when their defaults fit your setup.

The optional deployment administrator requires all three:
`DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, and
`DJANGO_SUPERUSER_PASSWORD`. Leave all three unset to skip automatic
creation. Existing configured accounts are preserved and promoted to staff
superusers without resetting their passwords.

The Build Command applies schema migrations, collects static files, and runs
`initialize_production`. That command initializes Documents from committed
`media/*.txt` files only when the database has none, then creates or reuses a
valid FAISS index from the current PostgreSQL Document IDs. It does not import
SQLite data or reset IDs. No Render Shell, manual index generation, or file
upload is required.

Render Free filesystems can be replaced across deploys or restarts. FAISS is
derived data, not persistent application state; if the index is missing or
stale at runtime, a request requiring retrieval rebuilds it from PostgreSQL
under a cross-process file lock. Gunicorn's default single worker limits
memory use. If rebuilding fails, the chat endpoint returns a controlled
temporary error.

Django serves static files using WhiteNoise. Render provides `$PORT`; do not
hard-code a production port or configure Nginx. Render's default TCP health
check applies; the project has no dedicated application health endpoint.

For the full environment and operational details, see
[the Render PostgreSQL initialization runbook](./docs/fresh-postgresql-initialization.md).
