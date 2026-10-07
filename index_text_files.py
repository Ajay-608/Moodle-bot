import django
import os
import re
import sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'moodlebot.settings')
django.setup()

from django.db import connection
from knowledge.models import Document

if connection.vendor != 'sqlite':
    raise SystemExit(
        'Refusing to run index_text_files.py on a non-SQLite database. '
        'This script deletes and recreates Document rows; use build_index.py '
        'to rebuild FAISS without changing the database.'
    )

if Document.objects.exists() and '--replace-existing' not in sys.argv[1:]:
    raise SystemExit(
        'Existing Documents were found. This script deletes all Document rows; '
        'rerun with --replace-existing only for an intentional local SQLite reset.'
    )

print(f"🗑️ Clearing {Document.objects.count()} existing documents...")
Document.objects.all().delete()

text_folder = 'media'
total_chunks = 0

for filename in os.listdir(text_folder):
    if filename.endswith('.txt'):
        filepath = os.path.join(text_folder, filename)
        print(f"\n📄 Reading {filename}...")

        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()

        text = re.sub(r'\n+', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        chunks = [text[i:i+500] for i in range(0, len(text), 500)]

        for i, chunk in enumerate(chunks):
            if chunk.strip():
                Document.objects.create(
                    title=f"{filename} — Part {i+1}",
                    content=chunk.strip(),
                    course_id=1
                )
                total_chunks += 1

        print(f"  ✅ Added {len(chunks)} chunks from {filename}")

print(f"\n✅ Done! Total chunks indexed: {total_chunks}")