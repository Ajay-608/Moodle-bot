"""Load committed course text into an empty database as deterministic chunks."""

import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from knowledge.models import Document


CHUNK_SIZE = 500


def source_chunks(source_dir):
    files = sorted(
        source_dir.glob("*.txt"),
        key=lambda path: (path.name.casefold(), path.name),
    )
    if not files:
        raise CommandError(f"No course text files found in {source_dir}.")

    for source in files:
        text = source.read_text(encoding="utf-8", errors="ignore")
        text = re.sub(r"\s+", " ", text).strip()
        for number, offset in enumerate(range(0, len(text), CHUNK_SIZE), start=1):
            content = text[offset:offset + CHUNK_SIZE].strip()
            if content:
                yield {
                    "title": f"{source.name} - Part {number}",
                    "content": content,
                    "course_id": 1,
                    "chunk_id": number,
                }


class Command(BaseCommand):
    help = (
        "Initialize Documents from committed media/*.txt files in an empty "
        "database; refuses to run if any Documents already exist."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        if Document.objects.exists():
            raise CommandError(
                "Documents already exist. This initializer never replaces or "
                "updates existing knowledge-base content."
            )

        source_dir = Path(settings.BASE_DIR) / "media"
        documents = list(source_chunks(source_dir))
        if not documents:
            raise CommandError(f"No non-empty course chunks found in {source_dir}.")

        Document.objects.bulk_create([Document(**document) for document in documents])
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {len(documents)} Document chunks from {source_dir}. "
                "Run build_index.py after verifying the content."
            )
        )
