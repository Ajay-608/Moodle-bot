import os
from pathlib import Path

import django
import faiss
import numpy as np

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "moodlebot.settings")
django.setup()

from django.conf import settings
from django.db import connection
from knowledge.models import Document
from sentence_transformers import SentenceTransformer


DIMENSION = 384
BATCH_SIZE = 64


def build_index():
    if connection.vendor != "postgresql":
        raise RuntimeError(
            "build_index.py requires the PostgreSQL database selected by DATABASE_URL. "
            "Set DATABASE_URL before building the production FAISS index."
        )

    documents = list(Document.objects.order_by("id").values_list("id", "content"))
    if not documents:
        raise RuntimeError(
            "No Documents found in PostgreSQL. Run "
            "'python manage.py initialize_knowledge_base' before building FAISS."
        )

    document_ids = np.asarray([item[0] for item in documents], dtype=np.int64)
    if len(np.unique(document_ids)) != len(document_ids):
        raise RuntimeError("Duplicate Document primary keys cannot be indexed.")

    model = SentenceTransformer("all-MiniLM-L6-v2")
    if model.get_sentence_embedding_dimension() != DIMENSION:
        raise RuntimeError(f"Expected {DIMENSION}-dimensional document embeddings.")

    index = faiss.IndexIDMap2(faiss.IndexFlatL2(DIMENSION))
    for offset in range(0, len(documents), BATCH_SIZE):
        batch = documents[offset:offset + BATCH_SIZE]
        vectors = model.encode(
            [content[:400] for _, content in batch],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        vectors = np.asarray(vectors, dtype=np.float32)
        if vectors.shape != (len(batch), DIMENSION) or not np.isfinite(vectors).all():
            raise RuntimeError("The embedding model returned invalid vectors.")
        ids = np.asarray([pk for pk, _ in batch], dtype=np.int64)
        index.add_with_ids(vectors, ids)

    if index.ntotal != Document.objects.count():
        raise RuntimeError(
            f"FAISS indexed {index.ntotal} vectors, but the database contains "
            f"{Document.objects.count()} Documents."
        )

    index_ids = faiss.vector_to_array(index.id_map)
    if set(index_ids.tolist()) != set(document_ids.tolist()):
        raise RuntimeError("FAISS IDs do not match the Document primary keys.")

    index_path = Path(settings.FAISS_INDEX_PATH)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = index_path.with_name(f".{index_path.name}.tmp")
    try:
        faiss.write_index(index, str(temporary_path))
        os.replace(temporary_path, index_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()

    print(
        f"Built FAISS index with {index.ntotal} vectors "
        f"for {len(documents)} Documents at {index_path}."
    )


if __name__ == "__main__":
    build_index()
