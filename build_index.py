import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'moodlebot.settings')
django.setup()

from knowledge.models import Document
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

print('Loading model...')
model = SentenceTransformer('all-MiniLM-L6-v2')

docs = Document.objects.all()
print(f'Found {docs.count()} documents')

embeddings = []
for i, doc in enumerate(docs):
    emb = model.encode([doc.content[:400]])[0]
    embeddings.append(emb)
    if i % 20 == 0:
        print(f'Processed {i}/{docs.count()}...')

embeddings = np.array(embeddings).astype('float32')
index = faiss.IndexFlatL2(384)
index.add(embeddings)
faiss.write_index(index, 'rag_index.faiss')
print(f'✅ FAISS index built with {index.ntotal} vectors and saved!')