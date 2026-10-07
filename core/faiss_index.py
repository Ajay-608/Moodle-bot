import hashlib
import json
import logging
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

import faiss
import numpy as np
from django.conf import settings

from knowledge.models import Document


logger = logging.getLogger(__name__)

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384
BATCH_SIZE = 64


class InvalidFAISSIndex(RuntimeError):
    pass


def index_path():
    return Path(settings.FAISS_INDEX_PATH)


def document_ids():
    return list(Document.objects.order_by("id").values_list("id", flat=True))


def document_signature():
    digest = hashlib.sha256()
    ids = []
    for document_id, content in (
        Document.objects.order_by("id")
        .values_list("id", "content")
        .iterator(chunk_size=BATCH_SIZE)
    ):
        ids.append(document_id)
        digest.update(str(document_id).encode("ascii"))
        digest.update(b"\0")
        digest.update((content or "").encode("utf-8"))
        digest.update(b"\0")
    return tuple(ids), digest.hexdigest()


def fingerprint_documents(documents):
    digest = hashlib.sha256()
    for document_id, content in documents:
        digest.update(str(document_id).encode("ascii"))
        digest.update(b"\0")
        digest.update((content or "").encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def metadata_path(path):
    path = Path(path)
    return path.with_name(f"{path.name}.metadata.json")


def create_embedding_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL_NAME)


@contextmanager
def index_build_lock(path):
    lock_path = Path(f"{path}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = lock_path.open("a+b")
    locked = False
    try:
        if os.name == "nt":
            import msvcrt

            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"\0")
                lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        locked = True

        yield
    finally:
        try:
            if locked and os.name == "nt":
                import msvcrt

                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            elif locked:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        finally:
            lock_file.close()


def validate_index(index, expected_ids):
    if not isinstance(index, faiss.IndexIDMap2):
        raise InvalidFAISSIndex(
            "FAISS index does not contain PostgreSQL Document IDs."
        )
    if index.d != EMBEDDING_DIMENSION:
        raise InvalidFAISSIndex(
            f"FAISS index dimension is {index.d}; expected {EMBEDDING_DIMENSION}."
        )
    if index.ntotal == 0:
        raise InvalidFAISSIndex("FAISS index contains no vectors.")
    if index.ntotal != len(expected_ids):
        raise InvalidFAISSIndex(
            f"FAISS index contains {index.ntotal} vectors for "
            f"{len(expected_ids)} current Documents."
        )

    indexed_ids = faiss.vector_to_array(index.id_map).astype(np.int64, copy=False)
    if len(np.unique(indexed_ids)) != len(indexed_ids):
        raise InvalidFAISSIndex("FAISS index contains duplicate Document IDs.")
    if set(indexed_ids.tolist()) != set(expected_ids):
        raise InvalidFAISSIndex(
            "FAISS index Document IDs do not match the current database."
        )
    return index


def load_valid_index(path, expected_ids, expected_fingerprint):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"FAISS index does not exist at {path}.")
    try:
        loaded_index = faiss.read_index(str(path))
        validate_index(loaded_index, expected_ids)
        metadata = json.loads(metadata_path(path).read_text(encoding="utf-8"))
        if metadata.get("model") != EMBEDDING_MODEL_NAME:
            raise InvalidFAISSIndex("FAISS embedding model metadata is incompatible.")
        if metadata.get("dimension") != EMBEDDING_DIMENSION:
            raise InvalidFAISSIndex("FAISS embedding dimension metadata is incompatible.")
        if metadata.get("document_ids") != list(expected_ids):
            raise InvalidFAISSIndex("FAISS metadata Document IDs are stale.")
        if metadata.get("document_fingerprint") != expected_fingerprint:
            raise InvalidFAISSIndex("FAISS index is stale for the current Documents.")
        return loaded_index
    except Exception as exc:
        if isinstance(exc, InvalidFAISSIndex):
            raise
        raise InvalidFAISSIndex(
            f"FAISS index or metadata at {path} is invalid."
        ) from exc


def _build_faiss_index(path, model=None, documents=None):
    path = Path(path or index_path())
    if documents is None:
        documents = list(
            Document.objects.order_by("id").values_list("id", "content")
        )
    if not documents:
        raise RuntimeError(
            "No Documents exist in the active database; initialize the knowledge "
            "base before building FAISS."
        )

    ids = [document_id for document_id, _ in documents]
    fingerprint = fingerprint_documents(documents)
    if len(set(ids)) != len(ids):
        raise RuntimeError("Duplicate Document IDs cannot be indexed.")
    if any(not content or not content.strip() for _, content in documents):
        raise RuntimeError("Documents with empty content cannot be indexed.")

    if model is None:
        model = create_embedding_model()
    if model.get_sentence_embedding_dimension() != EMBEDDING_DIMENSION:
        raise RuntimeError(
            f"{EMBEDDING_MODEL_NAME} must produce {EMBEDDING_DIMENSION}-dimensional "
            "embeddings."
        )

    index = faiss.IndexIDMap2(faiss.IndexFlatL2(EMBEDDING_DIMENSION))
    for offset in range(0, len(documents), BATCH_SIZE):
        batch = documents[offset:offset + BATCH_SIZE]
        vectors = np.asarray(
            model.encode(
                [content[:400] for _, content in batch],
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            ),
            dtype=np.float32,
        )
        if vectors.shape != (len(batch), EMBEDDING_DIMENSION):
            raise RuntimeError(
                "Embedding model returned an unexpected vector shape "
                f"{vectors.shape}; expected {(len(batch), EMBEDDING_DIMENSION)}."
            )
        if not np.isfinite(vectors).all():
            raise RuntimeError("Embedding model returned non-finite values.")

        batch_ids = np.asarray([document_id for document_id, _ in batch], dtype=np.int64)
        index.add_with_ids(vectors, batch_ids)

    validate_index(index, ids)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    metadata_file = metadata_path(path)
    metadata_descriptor, metadata_temporary_name = tempfile.mkstemp(
        prefix=f".{metadata_file.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    os.close(metadata_descriptor)
    metadata_temporary_path = Path(metadata_temporary_name)
    try:
        faiss.write_index(index, str(temporary_path))
        metadata_temporary_path.write_text(
            json.dumps(
                {
                    "model": EMBEDDING_MODEL_NAME,
                    "dimension": EMBEDDING_DIMENSION,
                    "document_fingerprint": fingerprint,
                    "document_ids": ids,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        os.replace(temporary_path, path)
        os.replace(metadata_temporary_path, metadata_file)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
        if metadata_temporary_path.exists():
            metadata_temporary_path.unlink()

    logger.info("Built FAISS index with %s vectors at %s", index.ntotal, path)
    return index


def build_faiss_index(path=None, model=None):
    path = Path(path or index_path())
    with index_build_lock(path):
        return _build_faiss_index(path, model=model)


def ensure_faiss_index(path=None, model_factory=None):
    path = Path(path or index_path())
    with index_build_lock(path):
        current_ids, fingerprint = document_signature()
        if not current_ids:
            raise RuntimeError(
                "No Documents exist in the active database; initialize the "
                "knowledge base before building FAISS."
            )

        try:
            index = load_valid_index(path, current_ids, fingerprint)
        except (FileNotFoundError, InvalidFAISSIndex) as exc:
            logger.warning("FAISS index requires rebuilding: %s", exc)
        else:
            return index

        documents = list(
            Document.objects.order_by("id").values_list("id", "content")
        )
        current_ids = [document_id for document_id, _ in documents]
        fingerprint = fingerprint_documents(documents)
        model = model_factory() if model_factory else None
        index = _build_faiss_index(path, model=model, documents=documents)
        actual_ids, actual_fingerprint = document_signature()
        if actual_ids != tuple(current_ids) or actual_fingerprint != fingerprint:
            raise RuntimeError(
                "Documents changed while rebuilding FAISS; retry index initialization."
            )
        return validate_index(index, current_ids)
