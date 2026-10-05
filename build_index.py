import os
import django
import numpy as np
import faiss

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "moodlebot.settings")
django.setup()

from knowledge.models import Document
from sentence_transformers import SentenceTransformer


MODEL_NAME = "all-MiniLM-L6-v2"
INDEX_PATH = "rag_index.faiss"


print("🔄 Loading embedding model...")
model = SentenceTransformer(MODEL_NAME)

docs = list(Document.objects.all().order_by("id"))

print(f"📚 Found {len(docs)} documents/chunks")

if not docs:
    print("❌ No documents found. Index was not created.")
    raise SystemExit(1)


embeddings = []
document_ids = []

for i, doc in enumerate(docs):

    text = (doc.content or "").strip()

    if not text:
        print(f"⚠️ Skipping empty document: {doc.id}")
        continue

    # Embed the COMPLETE chunk
    embedding = model.encode(
        text,
        normalize_embeddings=True
    )

    embeddings.append(embedding)
    document_ids.append(doc.id)

    if i % 100 == 0:
        print(f"Processed {i}/{len(docs)}...")


embeddings = np.asarray(embeddings, dtype="float32")
document_ids = np.asarray(document_ids, dtype="int64")


# Cosine similarity = inner product after normalization
dimension = embeddings.shape[1]

base_index = faiss.IndexFlatIP(dimension)

# Store the actual Django Document.id with each vector
index = faiss.IndexIDMap2(base_index)

index.add_with_ids(
    embeddings,
    document_ids
)


faiss.write_index(index, INDEX_PATH)

print()
print("======================================")
print("✅ FAISS index built successfully")
print(f"📊 Vectors: {index.ntotal}")
print(f"📐 Dimension: {dimension}")
print(f"💾 Saved: {INDEX_PATH}")
print("🔗 FAISS IDs = Django Document IDs")
print("======================================")