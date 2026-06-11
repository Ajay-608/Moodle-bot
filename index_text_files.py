import django
import os
import re
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'moodlebot.settings')
django.setup()

from knowledge.models import Document

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