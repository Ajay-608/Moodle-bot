import os
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import BaseCommand, CommandError, call_command
from django.db import connection

from core.faiss_index import ensure_faiss_index, index_path
from knowledge.models import Document


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Prepare a deployment database, initialize an empty knowledge base, "
        "and ensure a current FAISS index exists."
    )

    def handle(self, *args, **options):
        if not settings.DEBUG and connection.vendor != "postgresql":
            raise CommandError(
                "Production initialization requires PostgreSQL selected by "
                "DATABASE_URL."
            )
        try:
            connection.ensure_connection()
        except Exception as exc:
            logger.exception("Production initialization could not connect to database")
            raise CommandError(
                "The configured database is unavailable; production "
                "initialization could not continue."
            ) from exc

        self._ensure_deployment_admin()

        if Document.objects.exists():
            self.stdout.write("Knowledge-base Documents already exist; leaving them unchanged.")
        else:
            call_command("initialize_knowledge_base")

        try:
            index = ensure_faiss_index()
        except Exception as exc:
            logger.exception("Production FAISS initialization failed")
            self.stderr.write(
                self.style.ERROR(
                    "FAISS initialization failed; deployment initialization cannot "
                    "continue. See the logged exception for the root cause."
                )
            )
            raise CommandError("Could not ensure a valid FAISS index.") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Production initialization complete: {index.ntotal} FAISS vectors "
                f"at {index_path()}."
            )
        )

    def _ensure_deployment_admin(self):
        keys = (
            "DJANGO_SUPERUSER_USERNAME",
            "DJANGO_SUPERUSER_EMAIL",
            "DJANGO_SUPERUSER_PASSWORD",
        )
        values = {key: os.environ.get(key, "").strip() for key in keys}
        if not any(values.values()):
            self.stdout.write("Deployment admin variables are not configured; skipping.")
            return
        if not all(values.values()):
            raise CommandError(
                "Set DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_EMAIL, and "
                "DJANGO_SUPERUSER_PASSWORD together, or leave all three unset."
            )

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=values["DJANGO_SUPERUSER_USERNAME"],
            defaults={
                "email": values["DJANGO_SUPERUSER_EMAIL"],
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            user.set_password(values["DJANGO_SUPERUSER_PASSWORD"])
            user.save(update_fields=("password",))
            self.stdout.write("Created configured deployment administrator.")
        else:
            fields_to_update = []
            if not user.is_staff:
                user.is_staff = True
                fields_to_update.append("is_staff")
            if not user.is_superuser:
                user.is_superuser = True
                fields_to_update.append("is_superuser")
            if fields_to_update:
                user.save(update_fields=fields_to_update)
            self.stdout.write("Configured deployment administrator is ready.")
