"""LEGACY/OPTIONAL SQLite audit tool; production initialization uses no SQLite data."""

import argparse
import hashlib
import json
import sqlite3
import sys
import os
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote
from uuid import UUID

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "moodlebot.settings")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
django.setup()

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import connections
from django.db.models import Count


EXCLUDED_MODELS = {
    ("admin", "logentry"),
    ("contenttypes", "contenttype"),
    ("sessions", "session"),
    ("auth", "permission"),
}


def normalize(value):
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {str(key): normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize(item) for item in value]
    return value


def migrated_models():
    models = []
    for model in apps.get_models():
        label = (model._meta.app_label, model._meta.model_name)
        if label in EXCLUDED_MODELS or model._meta.proxy:
            continue
        if model._meta.app_label in {"auth"} and model is not get_user_model() and model is not Group:
            continue
        models.append(model)
    return sorted(models, key=lambda model: model._meta.label_lower)


def setup_source(path):
    source_path = Path(path).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"SQLite source database not found: {source_path}")
    uri = source_path.as_uri() + "?mode=ro"
    connections.databases["migration_source"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": uri,
        "OPTIONS": {"uri": True, "timeout": 30},
        "CONN_MAX_AGE": 0,
        "ATOMIC_REQUESTS": False,
        "AUTOCOMMIT": True,
        "CONN_HEALTH_CHECKS": False,
        "TIME_ZONE": None,
        "USER": "",
        "PASSWORD": "",
        "HOST": "",
        "PORT": "",
    }
    return source_path


def source_health(path):
    uri = f"file:{quote(path.as_posix(), safe='/:')}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
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
    print("SQLite integrity_check: ok")
    print("SQLite foreign_key_check violations: 0")


def row_snapshot(model, alias):
    fields = list(model._meta.concrete_fields)
    rows = {}
    for obj in model._base_manager.using(alias).all().iterator():
        pk = normalize(model._meta.pk.value_from_object(obj))
        rows[pk] = {
            field.attname: normalize(field.value_from_object(obj))
            for field in fields
        }
    return rows


def permission_key(alias, permission_id):
    permission = (
        Permission.objects.using(alias)
        .select_related("content_type")
        .get(pk=permission_id)
    )
    return (
        permission.content_type.app_label,
        permission.content_type.model,
        permission.codename,
    )


def permission_snapshot(alias):
    return set(
        Permission.objects.using(alias)
        .select_related("content_type")
        .values_list(
            "content_type__app_label",
            "content_type__model",
            "codename",
            "name",
        )
    )


def m2m_snapshot(model, alias):
    pairs_by_name = {}
    permission_cache = {}
    for field in model._meta.many_to_many:
        through = field.remote_field.through
        if not through._meta.auto_created:
            continue
        source_name = field.m2m_field_name()
        target_name = field.m2m_reverse_field_name()
        source_field = through._meta.get_field(source_name)
        target_field = through._meta.get_field(target_name)
        pairs = set()
        rows = through._base_manager.using(alias).values_list(
            source_field.attname, target_field.attname
        )
        for source_id, target_id in rows.iterator():
            target_model = target_field.remote_field.model
            if target_model is Permission:
                cache_key = (alias, target_id)
                if cache_key not in permission_cache:
                    permission_cache[cache_key] = permission_key(alias, target_id)
                target_id = permission_cache[cache_key]
            pairs.add((normalize(source_id), normalize(target_id)))
        pairs_by_name[field.name] = pairs
    return pairs_by_name


def foreign_key_orphans(alias):
    database = connections[alias]
    quote_name = database.ops.quote_name
    orphan_count = 0
    orphan_tables = []
    for model in apps.get_models(include_auto_created=True):
        if model._meta.proxy or model._meta.abstract:
            continue
        for field in model._meta.local_fields:
            if not field.is_relation or not field.many_to_one:
                continue
            target = field.remote_field.model
            sql = (
                f"SELECT COUNT(*) FROM {quote_name(model._meta.db_table)} child "
                f"LEFT JOIN {quote_name(target._meta.db_table)} parent "
                f"ON child.{quote_name(field.column)} = "
                f"parent.{quote_name(target._meta.pk.column)} "
                f"WHERE child.{quote_name(field.column)} IS NOT NULL "
                f"AND parent.{quote_name(target._meta.pk.column)} IS NULL"
            )
            try:
                with database.cursor() as cursor:
                    cursor.execute(sql)
                    count = cursor.fetchone()[0]
            except Exception as exc:
                raise RuntimeError(
                    f"Could not validate foreign keys for {model._meta.label}."
                ) from exc
            if count:
                orphan_count += count
                orphan_tables.append(f"{model._meta.db_table}.{field.column}={count}")
    if orphan_count:
        print(f"{alias} foreign-key orphan references: {orphan_count} ({', '.join(orphan_tables)})")
    else:
        print(f"{alias} foreign-key orphan references: 0")
    return orphan_count


def duplicate_values(model, alias, field_name, allow_empty=False):
    field = model._meta.get_field(field_name)
    queryset = model._base_manager.using(alias).values(field.attname).annotate(
        record_count=Count("pk")
    ).filter(record_count__gt=1)
    if allow_empty:
        queryset = queryset.exclude(**{f"{field.attname}__in": ["", None]})
    return queryset.count()


def audit_source(source_path):
    source_health(source_path)
    alias = "migration_source"
    models = migrated_models()
    content_type_model = apps.get_model("contenttypes", "ContentType")
    print(
        f"django_content_type: SQLite rows="
        f"{content_type_model._base_manager.using(alias).count()}"
    )
    print(f"auth.Permission: SQLite rows={Permission.objects.using(alias).count()}")
    for model in models:
        print(f"{model._meta.label}: SQLite rows={model._base_manager.using(alias).count()}")
    through_tables = set()
    for model in models:
        for field in model._meta.many_to_many:
            through = field.remote_field.through
            if through._meta.auto_created and through._meta.db_table not in through_tables:
                through_tables.add(through._meta.db_table)
                print(
                    f"{model._meta.label}.{field.name}: SQLite pairs="
                    f"{through._base_manager.using(alias).count()}"
                )

    User = get_user_model()
    user_count = User._base_manager.using(alias).count()
    duplicate_usernames = duplicate_values(User, alias, User.USERNAME_FIELD)
    print(f"Duplicate usernames: {duplicate_usernames}")
    if any(field.name == "email" for field in User._meta.fields):
        duplicate_emails = duplicate_values(User, alias, "email", allow_empty=True)
        print(f"Duplicate non-empty emails: {duplicate_emails}")
    document_model = apps.get_model("knowledge", "Document")
    document_count = document_model._base_manager.using(alias).count()
    empty_documents = document_model._base_manager.using(alias).filter(content="").count()
    print(f"Empty Document content: {empty_documents}")
    orphan_count = foreign_key_orphans(alias)
    if duplicate_usernames or empty_documents or orphan_count:
        raise RuntimeError("Source audit found duplicate usernames, empty Documents, or FK orphans.")
    if not user_count or not document_count:
        raise RuntimeError(
            "The SQLite source has no users or no Documents. Confirm that this is "
            "the intended migration database before exporting a fixture."
        )


def require_empty_target(alias, models):
    if connections[alias].vendor != "postgresql":
        raise RuntimeError("--require-empty requires DATABASE_URL to select PostgreSQL.")
    nonempty = []
    for model in models:
        count = model._base_manager.using(alias).count()
        if count:
            nonempty.append(f"{model._meta.label}={count}")
    through_tables = set()
    for model in models:
        for field in model._meta.many_to_many:
            through = field.remote_field.through
            if through._meta.auto_created and through._meta.db_table not in through_tables:
                through_tables.add(through._meta.db_table)
                count = through._base_manager.using(alias).count()
                if count:
                    nonempty.append(f"{through._meta.db_table}={count}")
    if nonempty:
        raise RuntimeError(
            "Target is not empty; fixture import is forbidden: " + ", ".join(nonempty)
        )
    print("PostgreSQL target schema exists and all migration data tables are empty.")


def compare_databases(source_path):
    alias = "migration_source"
    source_health(source_path)
    models = migrated_models()
    mismatches = []

    source_permissions = permission_snapshot(alias)
    target_permissions = permission_snapshot("default")
    print(
        f"auth.Permission natural keys: source={len(source_permissions)} "
        f"destination={len(target_permissions)} "
        f"missing={len(source_permissions - target_permissions)} "
        f"extra={len(target_permissions - source_permissions)}"
    )
    if source_permissions != target_permissions:
        mismatches.append("auth.Permission natural-key comparison")

    for model in models:
        source_rows = row_snapshot(model, alias)
        target_rows = row_snapshot(model, "default")
        source_ids = set(source_rows)
        target_ids = set(target_rows)
        missing = source_ids - target_ids
        extra = target_ids - source_ids
        changed = [
            pk for pk in source_ids & target_ids
            if source_rows[pk] != target_rows[pk]
        ]
        print(
            f"{model._meta.label}: source={len(source_rows)} destination={len(target_rows)} "
            f"missing={len(missing)} extra={len(extra)} changed={len(changed)}"
        )
        if missing or extra or changed:
            mismatches.append(model._meta.label)

        source_m2m = m2m_snapshot(model, alias)
        target_m2m = m2m_snapshot(model, "default")
        for field_name in source_m2m:
            source_pairs = source_m2m[field_name]
            target_pairs = target_m2m[field_name]
            missing_pairs = source_pairs - target_pairs
            extra_pairs = target_pairs - source_pairs
            print(
                f"{model._meta.label}.{field_name}: source_pairs={len(source_pairs)} "
                f"destination_pairs={len(target_pairs)} "
                f"missing={len(missing_pairs)} extra={len(extra_pairs)}"
            )
            if missing_pairs or extra_pairs:
                mismatches.append(f"{model._meta.label}.{field_name}")

        if model._meta.label_lower == "knowledge.document":
            source_hashes = {
                pk: hashlib.sha256(row["content"].encode("utf-8")).hexdigest()
                for pk, row in source_rows.items()
            }
            target_hashes = {
                pk: hashlib.sha256(row["content"].encode("utf-8")).hexdigest()
                for pk, row in target_rows.items()
            }
            if source_hashes != target_hashes:
                mismatches.append("knowledge.Document content hashes")
            else:
                print("Document content SHA-256 comparison: exact match")

    source_orphans = foreign_key_orphans(alias)
    target_orphans = foreign_key_orphans("default")
    if source_orphans or target_orphans:
        mismatches.append("foreign-key orphan validation")
    if mismatches:
        raise RuntimeError("Migration comparison failed: " + ", ".join(mismatches))
    print("EXACT SOURCE/DESTINATION VALIDATION PASSED.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", required=True, help="Path to the source SQLite database")
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--require-empty", action="store_true")
    args = parser.parse_args()

    source_path = setup_source(args.sqlite)
    models = migrated_models()
    if args.source_only:
        audit_source(source_path)
        print("SOURCE VALIDATION PASSED.")
        return
    if args.require_empty:
        source_health(source_path)
        require_empty_target("default", models)
        return
    if connections["default"].vendor != "postgresql":
        raise RuntimeError("Set DATABASE_URL to the PostgreSQL destination before comparison.")
    compare_databases(source_path)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"VALIDATION FAILED: {error}", file=sys.stderr)
        sys.exit(1)
