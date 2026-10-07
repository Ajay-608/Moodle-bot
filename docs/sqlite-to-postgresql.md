# Legacy SQLite migration preparation

SQLite-to-PostgreSQL data migration is **not part of the production plan**.
Production starts with a fresh PostgreSQL database; the old local SQLite
database, its users, documents, chats, and other records are not imported.

The scripts in `scripts/export_sqlite_migration.py` and
`scripts/validate_database_migration.py` are retained only as optional legacy
local audit/backup tools. They are not used by the active deployment process.
Do not use their fixtures for production initialization.

Use the [fresh PostgreSQL initialization runbook](fresh-postgresql-initialization.md).
