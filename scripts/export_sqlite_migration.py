"""LEGACY/OPTIONAL SQLite fixture helper; not used by fresh production setup."""

import os
import sqlite3
import stat
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import django

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "moodlebot.settings")
django.setup()

from django.conf import settings
from django.core.management import call_command
from django.db import connections


EXCLUDED_MODELS = (
    "contenttypes",
    "auth.permission",
    "sessions.session",
    "admin.logentry",
)


def verify_sqlite(path):
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity_check failed: {integrity}")
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(
                f"SQLite foreign_key_check found {len(violations)} violation(s)."
            )
    finally:
        connection.close()


def main():
    if settings.DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3":
        raise RuntimeError("Fixture export must run against the local SQLite database.")
    source = Path(settings.DATABASES["default"]["NAME"]).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"SQLite database not found: {source}")

    verify_sqlite(source)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path(tempfile.mkdtemp(prefix="moodlebot-migration-"))
    if os.name == "posix":
        output_dir.chmod(stat.S_IRWXU)
    backup = output_dir / f"moodlebot-{timestamp}.migration-backup.sqlite3"
    fixture = output_dir / f"moodlebot-{timestamp}.fixture.json"

    source_db = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)
    try:
        with sqlite3.connect(backup) as backup_db:
            source_db.backup(backup_db)
    finally:
        source_db.close()
    verify_sqlite(backup)

    default_connection = connections["default"]
    default_connection.close()
    default_connection.settings_dict["NAME"] = str(backup)
    try:
        with fixture.open("x", encoding="utf-8") as output:
            if os.name == "posix":
                os.chmod(fixture, stat.S_IRUSR | stat.S_IWUSR)
            call_command(
                "dumpdata",
                *[f"--exclude={model}" for model in EXCLUDED_MODELS],
                "--natural-foreign",
                "--indent=2",
                stdout=output,
            )
    except Exception:
        fixture.unlink(missing_ok=True)
        raise
    finally:
        default_connection.close()

    print(f"Verified SQLite backup: {backup}")
    print(f"Private migration fixture: {fixture}")
    print(
        "The source database was opened read-only. Preserve these files securely; "
        "do not commit or upload them."
    )


if __name__ == "__main__":
    main()
