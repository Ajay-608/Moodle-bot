# Fresh Render PostgreSQL initialization and deployment

## Current target and data policy

The current planned production architecture is:

```text
GitHub
  ↓
Render Web Service
  ↓
Gunicorn
  ↓
Django
  ↓
fresh Render PostgreSQL
```

This runbook documents application configuration and one-time initialization.
Render resources are configured separately in the Render Dashboard. Prior AWS
EC2/RDS/Nginx guidance is superseded and is not the current deployment target.

Production starts with a fresh PostgreSQL database. Do not import SQLite
fixtures or migrate old SQLite data. Old users/password hashes, profiles,
chats/messages, Documents, feedback, learning gaps, surveys, primary keys, and
the old `rag_index.faiss` are not reused. Create a new superuser. Public
registration creates student accounts; administrators control teacher and
administrator privileges.

The committed `media/*.txt` files are the authoritative knowledge source.
`database_dataset.json` is an alternate legacy corpus and is not part of
production initialization.

## Phase 1 — GitHub

The repository is `Ajay-608/Moodle-bot`; the Render Web Service deploys the
reviewed `main` branch. With Auto-Deploy enabled, pushes to `main` trigger
deployments.

No `render.yaml` is included. Configure services manually in the Render
Dashboard; this avoids creating services/databases just by applying a
Blueprint.

## Phase 2 — Render PostgreSQL

1. Create a new Render PostgreSQL database manually.
2. Prefer the internal connection URL when the database and Web Service share
   a Render region. Keep its credentials secret.
3. Add the database URL to the Web Service's `DATABASE_URL` environment
   variable in Render. Do not commit or print the value.

The Django settings select PostgreSQL from `DATABASE_URL`. SQLite is only the
local-development fallback when `DEBUG=True`; startup fails if `DATABASE_URL`
is missing with `DEBUG=False`.

## Phase 3 — Render Web Service

Create a Web Service connected to the repository and reviewed branch. Choose
Python 3 and set `PYTHON_VERSION=3.11.9`, matching the project's FAISS/Torch
dependency pins and `runtime.txt`.

Configure these exact commands:

**Build Command**

```text
pip install -r requirements.txt && python manage.py collectstatic --noinput
```

**Start Command**

```text
gunicorn --bind 0.0.0.0:$PORT moodlebot.wsgi:application
```

Render requires a public Web Service to listen on `0.0.0.0`; `$PORT` is
provided by Render ([port binding documentation](https://render.com/docs/web-services)).
Do not hard-code a port. `gunicorn` and the required
database, static, FAISS, and embedding packages are already in
`requirements.txt`.

### Environment variables

Configure these in the Render Web Service environment:

| Name | Value |
|---|---|
| `SECRET_KEY` | A newly generated secret, stored only in Render |
| `DEBUG` | `False` |
| `DATABASE_URL` | The fresh Render PostgreSQL internal connection URL |
| `ALLOWED_HOSTS` | The actual Render hostname, without `https://` |
| `CSRF_TRUSTED_ORIGINS` | The actual HTTPS origin, including `https://` |
| `GROQ_API_KEY` | Groq key if Groq is used |
| `OPENROUTER_API_KEY` | OpenRouter key if OpenRouter fallback is used |
| `LLM_MODEL` | Optional; code default is `llama-3.1-8b-instant` |
| `OPENROUTER_MODEL` | Optional; code default is `meta-llama/llama-3.1-8b-instruct:free` |
| `CORS_ALLOWED_ORIGINS` | Optional comma-separated origins only if a cross-origin client is used |
| `FAISS_INDEX_PATH` | Set to `/var/data/rag_index.faiss` when using the persistent disk below |
| `PYTHON_VERSION` | `3.11.9` for the Render Python runtime |

At least one provider API key is needed for hosted model responses. The
`SECRET_KEY` and database URL must never be added to `.env.example`, source
files, or logs. `.env.example` contains placeholders only. The code defaults
`DEBUG` to `False`, so a missing Render setting does not accidentally enable
debug mode.

After Render assigns the service hostname, set `ALLOWED_HOSTS` to that
hostname (no scheme) and set `CSRF_TRUSTED_ORIGINS` to its HTTPS origin.
Do not use an invented hostname. `SECURE_PROXY_SSL_HEADER` and secure session
and CSRF cookies are already configured for a TLS-terminating proxy.

### Static files and health checks

Django's existing WhiteNoise middleware serves the output of
`collectstatic`; `STATIC_ROOT` is `staticfiles/`. Render does not need Nginx.
The service logs to stdout/stderr, which Render captures.

There is no dedicated health URL such as `/api/health`. Keep Render's default
TCP port health check; do not configure a nonexistent route. `/login/` is a
public page but is not a database-readiness check.

## Phase 4 — One-time database initialization

The Build Command does not run migrations or seed data. After the first Web
Service deploy, open the service's Dashboard **Shell** for the live instance
(not an isolated ephemeral shell), verify it has the configured
`DATABASE_URL`, and run these once, in order:

```text
python manage.py migrate
python manage.py createsuperuser
python manage.py initialize_knowledge_base
python build_index.py
python manage.py check
```

`createsuperuser` is interactive. Do not create a default production account
or put admin credentials in source. This procedure neither imports SQLite nor
runs `populate_sample_data`.

`initialize_knowledge_base` reads committed text files in deterministic
filename order, normalizes whitespace, and creates 500-character chunks
atomically. PostgreSQL assigns new Document IDs. The command refuses to run
when any Documents already exist and never deletes/replaces them.

## Phase 5 — FAISS generation and storage

`build_index.py` uses the database selected by `DATABASE_URL` and refuses a
non-PostgreSQL database or an empty Documents table. It loads all current
PostgreSQL Documents, generates normalized `all-MiniLM-L6-v2` embeddings
(384 dimensions), maps each vector to the corresponding PostgreSQL
`Document.id`, verifies the exact ID set, count, dimensions, uniqueness, and
finite values, then atomically writes `FAISS_INDEX_PATH`.

The generated file is not committed. The old SQLite FAISS index is not used.
The chat code reports an explicit error if the generated index is missing or
invalid; it does not silently return a keyword/default response as if RAG had
succeeded.

### Render filesystem implications

Render's default service filesystem is ephemeral. Files written there are lost
on redeploy/restart ([Render disk documentation](https://render.com/docs/disks));
a Free Web Service also loses local changes on spin-down
([Free instance limitations](https://render.com/docs/free)).
The simplest persistent option for this single-instance design is a Render
persistent disk:

1. Choose a compatible paid Web Service plan (check current Render plan
   availability/pricing; no price or free availability is promised).
2. Attach a disk mounted at `/var/data`.
3. Set `FAISS_INDEX_PATH=/var/data/rag_index.faiss`.
4. Run `python build_index.py` from the Dashboard Shell attached to the live
   service instance after database initialization. Shell/SSH availability
   depends on the service type and plan
   ([Render shell documentation](https://render.com/docs/ssh)).

Keep this local-index Web Service to one instance: a mounted local disk and
FAISS file are not a shared index across scaled service instances.
Render notes that attaching a disk also prevents zero-downtime deploys, so
expect a brief service interruption during deploys
([disk limitations](https://render.com/docs/disks)).

Only files under the mount path persist. Do not use Render's isolated
ephemeral shell for this build: its files are discarded when that shell exits
and are not the live Web Service filesystem. Without a persistent disk, rerun
`python build_index.py` against the active instance after each redeploy,
restart, or spin-down before RAG chat is available. The application remains
available for non-RAG pages while the index is absent. Once the file exists,
the next chat request loads it into the process; a service restart is not
needed just to refresh the in-memory index.

The index can be checked from the service shell:

```text
python manage.py shell -c "from knowledge.models import Document; print('PostgreSQL Documents:', Document.objects.count())"
python manage.py shell -c "import faiss; from django.conf import settings; index = faiss.read_index(str(settings.FAISS_INDEX_PATH)); print('FAISS vectors:', index.ntotal)"
```

The printed Document and vector counts should match. The build command itself
also checks the exact primary-key set and count.

## Phase 6 — Production validation

After setup:

1. Open the actual Render service URL and confirm the login page loads.
2. Register a student account and verify normal login/logout.
3. Sign in as the newly created superuser and verify admin access.
4. Ask an in-scope database-course question and verify retrieved sources.
5. Ask an out-of-scope question and inspect the response behavior.
6. Check Render logs for database, static-file, embedding, or provider errors.

Do not claim PostgreSQL connectivity, a deployed service, or a working hosted
RAG index until these steps have actually been run.

## Normal future deployments

The normal Build and Start Commands above do not run migrations,
`createsuperuser`, `initialize_knowledge_base`, sample-data seeding, SQLite
fixture export/import, or legacy content loaders. Run schema migrations as a
controlled operation when model changes require them. Rebuild the FAISS index
after corpus updates, and after restarts if the service is not using a
persistent disk.

`populate_sample_data`, `index_text_files.py`, `load_database_dataset.py`,
`manage.py load_database_topics`, and the SQLite fixture/audit scripts are
local/legacy/optional tools only, not normal production commands.
