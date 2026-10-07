# MoodleBot — Quick Start

**Current production target:** GitHub → Render Web Service → Gunicorn → Django
→ fresh Render PostgreSQL. This repository's Render conversion is preparation
only; do not consider a deployment complete until you create and configure the
services in the Render Dashboard.

## Local development

Use Python 3.11. Copy `.env.example` to `.env`, set a local `SECRET_KEY`, set
`DEBUG=True`, and leave `DATABASE_URL` blank to use local SQLite.

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py populate_sample_data
python manage.py runserver
```

Sample data is local-only. Never run `populate_sample_data` in production.

## Render configuration

1. Ensure the reviewed Render-ready commit is pushed to
   `Ajay-608/Moodle-bot`. The current working branch is
   `agents/moodlebot-login-page-loading-problem-i-have-an`; these local
   uncommitted changes must be reviewed and published before Render can build
   them.
2. In Render, create a **PostgreSQL** database. Use its internal connection
   URL for the web service when both services are in the same Render region.
   Keep the URL private.
3. Create a **Web Service** from the GitHub repository and the branch
   containing the reviewed changes. Choose Python 3 and configure
   `PYTHON_VERSION=3.11.9`.
4. Configure these commands:

   **Build Command**

   ```text
   pip install -r requirements.txt && python manage.py collectstatic --noinput
   ```

   **Start Command**

   ```text
   gunicorn --bind 0.0.0.0:$PORT moodlebot.wsgi:application
   ```

   Render supplies `PORT`; do not replace it with a hard-coded port.
5. Set the environment variables listed in
   [the deployment runbook](./docs/fresh-postgresql-initialization.md).
   Set `DEBUG=False`. After Render assigns the service hostname, use the actual
   hostname (without scheme) in `ALLOWED_HOSTS`, and its `https://` origin in
   `CSRF_TRUSTED_ORIGINS`.
6. Render's default TCP health check is sufficient. There is no dedicated
   application health endpoint in the current project; do not configure a
   nonexistent `/api/health` route.
7. For reliable FAISS availability, attach a persistent disk mounted at
   `/var/data` and set `FAISS_INDEX_PATH=/var/data/rag_index.faiss`. This
   requires a compatible paid service plan. Without a disk, the index is lost
   on restart, deploy, or free-instance spin-down and must be rebuilt before
   chat retrieval is available. Keep this design to a single service
   instance; the disk is not shared across multiple instances.

## One-time fresh database setup

After the Web Service has successfully deployed, use the service's Dashboard
Shell connected to the live instance (not an isolated ephemeral shell) and
run these commands **once, in order**:

```text
python manage.py migrate
python manage.py createsuperuser
python manage.py initialize_knowledge_base
python build_index.py
python manage.py check
```

The initializer loads committed `media/*.txt` sources into deterministic,
normalized 500-character chunks. It runs atomically and refuses to run if any
Documents already exist. `build_index.py` reads the current PostgreSQL
Documents, generates normalized 384-dimensional `all-MiniLM-L6-v2`
embeddings, maps each vector to its PostgreSQL `Document.id`, validates exact
IDs and counts, and atomically writes the index.

The database is fresh. Old SQLite users/passwords, chats/messages, Documents,
feedback, learning gaps, surveys, and IDs are not migrated. The old FAISS
index is not reused. Create a new production superuser; users register
normally after launch. Public registration creates students only.

Routine deploys run the Build and Start Commands above. They do **not** run
`migrate`, `createsuperuser`, `initialize_knowledge_base`,
`populate_sample_data`, SQLite fixture tools, or destructive legacy loaders
automatically. Run migrations as a controlled operation when schema changes
are introduced.

Check Render's current pricing and plan limitations before creating services
or a persistent disk; this guide does not promise that any Render service is
free.
