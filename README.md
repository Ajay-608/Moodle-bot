# MoodleBot

MoodleBot is a Django learning chatbot with account roles, course-document
retrieval, FAISS similarity search, and Groq/OpenRouter chat completions.

**Current deployment target:** GitHub → Render Web Service → Gunicorn →
Django → fresh Render PostgreSQL. This is preparation only; no Render service
or database has been created or deployed.

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

Use the manual Render Dashboard configuration in
[QUICK_START.md](./QUICK_START.md) and the complete
[Render PostgreSQL initialization runbook](./docs/fresh-postgresql-initialization.md).
The active service uses Django's existing WhiteNoise static-file middleware;
Render does not need an Nginx configuration.

Render build command:

```text
pip install -r requirements.txt && python manage.py collectstatic --noinput
```

Render start command (binds to Render's assigned `PORT`):

```text
gunicorn --bind 0.0.0.0:$PORT moodlebot.wsgi:application
```

Configure production environment variables in Render, not in Git. The
production database is fresh: no SQLite users, chats, messages, Documents,
feedback, learning data, surveys, IDs, or FAISS index are migrated or reused.
Create a new superuser and initialize the knowledge corpus once after the
service and database are ready. Normal deploys do not seed sample data or run
legacy loaders.

Render's default filesystem is ephemeral. For an index that survives deploys
and restarts, attach a Render persistent disk at `/var/data` and set
`FAISS_INDEX_PATH=/var/data/rag_index.faiss`. Persistent disks require a
compatible paid service plan; check current Render pricing and availability.
Without a disk, the generated index must be rebuilt after every redeploy,
restart, or free-service spin-down. Keep this local-index design to one
service instance. The application reports a clear RAG error instead of
silently returning fabricated retrieval results when the index is missing.

## RAG details

- Embeddings: `all-MiniLM-L6-v2`, 384 dimensions.
- FAISS IDs are the fresh PostgreSQL `Document.id` values.
- `python build_index.py` validates the dimensions, count, and ID set, then
  writes a generated FAISS file atomically at `FAISS_INDEX_PATH`.
- The generated index is not committed. The legacy SQLite index is not used.

The SQLite fixture tools and document loaders are legacy/optional only. See
[the SQLite migration note](./docs/sqlite-to-postgresql.md); production does
not migrate SQLite data.
