# SQLite-to-PostgreSQL migration status

SQLite-to-PostgreSQL data migration is **not part of the current production
plan**. The current target is a fresh Render PostgreSQL database.

The production workflow applies Django migrations, creates a new superuser,
and initializes fresh Documents from committed course text files. Old SQLite
users/password hashes, profiles, chats/messages, Documents, feedback, learning
gaps, surveys, IDs, and the old FAISS index are not imported or reused.

The scripts in `scripts/export_sqlite_migration.py` and
`scripts/validate_database_migration.py` are legacy/optional local audit and
fixture tools only. They are not part of Render setup, normal deployments, or
the active fresh-database workflow. Do not run them against production.

See the [fresh Render PostgreSQL runbook](./fresh-postgresql-initialization.md).
Prior AWS EC2/RDS instructions are historical and superseded.
