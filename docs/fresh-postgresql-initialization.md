# Fresh PostgreSQL initialization and AWS deployment

Production is intentionally initialized with a **fresh Amazon RDS PostgreSQL
database**. The old SQLite database is legacy/archive data and is not migrated.
Old users, profiles, chat history, feedback, learning data, surveys, Document
IDs, and FAISS IDs do not appear in production. Create a new superuser in
PostgreSQL; users register normally after launch.

The committed `media/*.txt` course files are the authoritative source for the
existing chunked course corpus: they are the source consumed by the prior
`index_text_files.py` setup and represent the larger source materials. The
separate `database_dataset.json` is an alternate curated Q&A corpus with its
own legacy loaders. It is not part of the production initialization path.

## A. Local development

Install dependencies, copy `.env.example` to `.env`, set a fresh local
`SECRET_KEY`, set `DEBUG=True`, and leave `DATABASE_URL` blank to use the local
SQLite fallback.

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py populate_sample_data
python manage.py runserver
```

`populate_sample_data` is for local development only and refuses to run with
`DEBUG=False`. It does not reset existing users, passwords, roles, profiles,
chats, messages, Documents, learning gaps, feedback, or surveys.

## B. Fresh PostgreSQL initialization

First create/configure a fresh PostgreSQL database (RDS when AWS resources are
created). Install the application dependencies and supply `DATABASE_URL`,
`SECRET_KEY`, `ALLOWED_HOSTS`, and `CSRF_TRUSTED_ORIGINS` through the trusted
process environment or an approved secret manager. Also configure `DEBUG=False`
and the AI provider secrets needed by the application. Do not put real
credentials in source files, `.env.example`, Git, or logs.

The accepted URL form is:

```text
postgresql://DB_USER:DB_PASSWORD@DB_HOST:5432/DB_NAME?sslmode=require
```

Configure the production environment securely (for example, via the EC2
service's environment/secret configuration after EC2 exists):

```text
DATABASE_URL=<fresh-PostgreSQL-connection-URL>
SECRET_KEY=<fresh-secret>
ALLOWED_HOSTS=<actual-hostname>
CSRF_TRUSTED_ORIGINS=https://<actual-hostname>
DEBUG=False
GROQ_API_KEY=<provider-secret>
OPENROUTER_API_KEY=<provider-secret>
```

These are variable names and placeholders, not shell assignments or real
credentials. Do not paste secrets into a shell command, source file, or log.

The settings use PostgreSQL when `DATABASE_URL` is set, use SQLite only when
`DEBUG=True` for local development, and fail startup if `DATABASE_URL` is
missing with `DEBUG=False`. With the environment configured and the working
directory set to the project root, run these commands in order against the
fresh PostgreSQL database:

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

The new administrator is created directly in PostgreSQL. No previous user
account or password is imported. Django creates the authentication superuser;
when that account first reaches an application role-aware view, MoodleBot
creates its missing `UserProfile` with the admin role.

`initialize_knowledge_base` reads `media/*.txt` in deterministic filename
order, normalizes whitespace, and splits each source into 500-character
chunks with stable source/part titles and per-file chunk numbers. PostgreSQL
assigns fresh Document primary keys. It runs atomically and refuses to run if
any Documents already exist; it never deletes or updates existing content. If
the command fails, diagnose the problem before retrying. The legacy loaders
`index_text_files.py`, `load_database_dataset.py`, and
`manage.py load_database_topics` are not part of production initialization;
they can overwrite/delete content and/or only support local SQLite.

## C. Knowledge documents/chunks and FAISS

`build_index.py` requires the active database to be PostgreSQL and fails if it
has zero Documents. It embeds every current Document using
`all-MiniLM-L6-v2` (384 dimensions) with normalized vectors, maps each vector
to the new PostgreSQL `Document.id`, verifies dimensions, unique IDs, exact ID
set and count, then atomically writes a new `rag_index.faiss`. Never copy or
reuse the old SQLite FAISS file. Rebuild the index from PostgreSQL whenever
the Document corpus changes or the EC2 filesystem/index is replaced.

## D. AWS deployment preparation (future; not performed)

The intended architecture is:

```text
Internet
   ↓
Nginx
   ↓
Gunicorn
   ↓
Django
   ↓
Amazon RDS PostgreSQL
```

This is a plan only. No RDS or EC2 resource, DNS record, HTTPS certificate, or
deployment exists or has been configured or tested. After resources are
created, run Gunicorn as a service for `moodlebot.wsgi:application`, bind it
to a local/private interface, and configure Nginx as the reverse proxy.
Restrict RDS network access to the application host/security group. Keep the
freshly built FAISS index on the EC2 filesystem initially.

For example, the Gunicorn service can start the application with:

```bash
gunicorn moodlebot.wsgi:application --bind 127.0.0.1:8000 --workers 1 --timeout 120
```

Configure Nginx to proxy to that local Gunicorn listener; do not expose the
Gunicorn port publicly. Nginx must set `X-Forwarded-Proto` correctly for
Django's proxy HTTPS setting. Secure cookies are enabled when `DEBUG=False`.
Use actual hostname and secret values only after those are configured securely;
no endpoint, username, password, IP, ARN, domain, or secret is assumed here.

Users register normally after the application goes live. Public registration
creates student accounts only; administrators control teacher/admin accounts.
Do not add fixture import, `populate_sample_data`, `index_text_files.py`, or
the legacy dataset loaders to the production deployment workflow.

## E. Normal future deployments

Once initialized, routine code updates may run:

```powershell
python manage.py migrate
python manage.py collectstatic --noinput
```

Do not rerun the one-time knowledge initializer after content exists. Rebuild
FAISS from the active PostgreSQL data with `python build_index.py` only when
the Document corpus/index needs updating. Normal deployments never import
SQLite fixtures or recreate Document rows.

No AWS resources, PostgreSQL connection, migration, EC2 deployment, Gunicorn
service, Nginx configuration, DNS, or HTTPS setup has been performed by this
runbook.
