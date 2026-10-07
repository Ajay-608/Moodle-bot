# MoodleBot — Quick Start

**Production target:** AWS EC2 + Nginx + Gunicorn + Amazon RDS PostgreSQL.
AWS resources have not been created. Production will use a fresh PostgreSQL
database; old SQLite data is not migrated.

## Local development

Requirements: Python 3.11 and Git.

```powershell
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env`, set a fresh local `SECRET_KEY`, set `DEBUG=True`,
and leave `DATABASE_URL` blank for the local SQLite fallback.

```powershell
python manage.py migrate
python manage.py populate_sample_data
python manage.py runserver
```

Sample data is local development only; the command refuses to run when
`DEBUG=False`. The destructive legacy content loaders are not needed for local
login/development and must not be used for production initialization.

## Fresh PostgreSQL initialization

After the PostgreSQL database is created, securely configure `DATABASE_URL`,
`SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DEBUG=False`, and
required provider secrets through the environment/secret manager. Install
dependencies and run the following in order:

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py initialize_knowledge_base
python build_index.py
python manage.py check
python manage.py test
python manage.py collectstatic --noinput
```

The one-time knowledge initializer loads committed `media/*.txt` source files
into deterministic 500-character chunks. It refuses to run if Documents
already exist. Run `build_index.py` after initialization; it requires
PostgreSQL and creates a new FAISS index using the new PostgreSQL
`Document.id` values, with 384-dimensional normalized embeddings from
`all-MiniLM-L6-v2`. Do not reuse the old SQLite index.

Production does not migrate SQLite data: old users/profiles, chats/messages,
Documents, feedback, learning gaps, surveys, and old IDs do not appear. Create
a new PostgreSQL superuser; users register normally after launch. Public
registration creates students only. `populate_sample_data` is local-only and
must not be run in production.

## Planned AWS deployment

Set `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`,
`DATABASE_URL`, and AI provider secrets in the EC2 process environment or an
approved secrets mechanism. Do not commit credentials or invent endpoint or
domain values before AWS resources exist.

Serve `moodlebot.wsgi:application` with Gunicorn bound locally/private-side,
behind Nginx. Configure Nginx HTTPS and `X-Forwarded-Proto` before production
traffic. Store the newly generated `rag_index.faiss` on the EC2 filesystem.
This is preparation only: no RDS or EC2 resources, PostgreSQL connection,
DNS, HTTPS, Nginx configuration, or deployment have been performed or tested.

## Normal future deployments

Routine deployments run migrations and collect static files. They do not run
`initialize_knowledge_base`, sample-data seeding, SQLite fixture tools, or
destructive content loaders. Rebuild FAISS from the current PostgreSQL
Documents only when the corpus/index needs an update.
