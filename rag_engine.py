import logging
import os
import re
import threading

import numpy as np
import requests

from core.faiss_index import (
    EMBEDDING_DIMENSION,
    create_embedding_model,
    document_signature,
    ensure_faiss_index,
    index_path,
    metadata_path,
)
from knowledge.models import Document


logger = logging.getLogger(__name__)


class RAGUnavailableError(RuntimeError):
    """Raised when retrieval cannot safely use a current FAISS index."""


class RAGEngine:
    def __init__(self):
        self.model = None
        self.index = None
        self._document_ids = None
        self._document_fingerprint = None
        self._index_file_signature = None
        self._model_lock = threading.Lock()
        self.groq_url = "https://api.groq.com/openai/v1/chat/completions"
        self.groq_api_key = os.environ.get("GROQ_API_KEY")
        self.groq_model = os.environ.get("LLM_MODEL", "llama-3.1-8b-instant")
        self.openrouter_url = "https://openrouter.ai/api/v1/chat/completions"
        self.openrouter_api_key = os.environ.get("OPENROUTER_API_KEY")
        self.openrouter_model = os.environ.get(
            "OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free"
        )

    def _get_model(self):
        if self.model is None:
            with self._model_lock:
                if self.model is None:
                    model = create_embedding_model()
                    if model.get_sentence_embedding_dimension() != EMBEDDING_DIMENSION:
                        raise RuntimeError(
                            f"{EMBEDDING_MODEL_NAME} must produce "
                            f"{EMBEDDING_DIMENSION}-dimensional embeddings."
                        )
                    self.model = model
        return self.model

    @staticmethod
    def _file_signature():
        try:
            index_stat = index_path().stat()
            metadata_stat = metadata_path(index_path()).stat()
        except FileNotFoundError:
            return None
        return (
            index_stat.st_mtime_ns,
            index_stat.st_size,
            metadata_stat.st_mtime_ns,
            metadata_stat.st_size,
        )

    def _ensure_index(self):
        try:
            current_ids, current_fingerprint = document_signature()
            signature = self._file_signature()
            if (
                self.index is not None
                and current_ids == self._document_ids
                and current_fingerprint == self._document_fingerprint
                and signature is not None
                and signature == self._index_file_signature
            ):
                return self.index

            index = ensure_faiss_index(model_factory=self._get_model)
            self._document_ids, self._document_fingerprint = document_signature()
            self._index_file_signature = self._file_signature()
            self.index = index
            return index
        except Exception as exc:
            logger.exception("Unable to prepare a current FAISS index")
            raise RAGUnavailableError(
                "The knowledge index is temporarily unavailable. "
                "Please try again shortly."
            ) from exc

    @staticmethod
    def clean_text(text):
        text = re.sub(r"#+\s*", "", text)
        text = re.sub(r"\*+", "", text)
        text = re.sub(r"-\s+", "", text)
        text = re.sub(r"\n+", " ", text)
        return text.strip()

    def search(self, query, k=3):
        index = self._ensure_index()
        try:
            query_embedding = np.asarray(
                self._get_model().encode(
                    [query],
                    normalize_embeddings=True,
                    convert_to_numpy=True,
                ),
                dtype=np.float32,
            )
            if query_embedding.shape != (1, EMBEDDING_DIMENSION):
                raise RuntimeError(
                    "Query embedding has an unexpected dimension; "
                    "the configured embedding model may have changed."
                )
            if not np.isfinite(query_embedding).all():
                raise RuntimeError("Query embedding contains non-finite values.")

            distances, indices = index.search(query_embedding, max(1, k))
            requested_ids = [int(pk) for pk in indices[0] if pk >= 0]
            documents_by_id = Document.objects.in_bulk(requested_ids)
            docs = [documents_by_id[pk] for pk in requested_ids if pk in documents_by_id]
            if len(docs) != len(requested_ids):
                self.index = None
                raise RuntimeError(
                    "FAISS returned Document IDs that no longer exist in the database."
                )
            return docs, distances[0].tolist()
        except Exception as exc:
            logger.exception("FAISS retrieval failed")
            if isinstance(exc, RAGUnavailableError):
                raise
            raise RAGUnavailableError(
                "The knowledge index is temporarily unavailable. "
                "Please try again shortly."
            ) from exc

    def _call_openai_style(self, url, api_key, model, prompt, timeout=30, max_tokens=500):
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.1,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        if not content:
            raise RuntimeError(f"Provider returned empty content (model: {model})")
        return content.strip()

    def generate_response(self, query, context_docs, conversation_history=None):
        logger.info("RAG received %s context documents", len(context_docs))

        if not context_docs:
            logger.warning("No relevant documents were returned by FAISS")
            return {
                "answer": (
                    "Database Systems course covers SQL, JOINs, and normalization. "
                    "Try asking: 'Explain SQL JOINs' or 'What is 3NF?'"
                ),
                "confidence": 0.85,
                "sources": ["CS401 Course"],
            }

        context = "\n\n---\n\n".join([
            f"{doc.title}\n{self.clean_text(doc.content[:200])}"
            for doc in context_docs[:3] if doc.content
        ])
        history = "\n".join(
            f"{message['role']}: {message['content']}"
            for message in (conversation_history or [])[-10:]
            if message.get("role") in {"user", "assistant"}
        )
        prompt = f"""You are MoodleBot, a friendly database systems tutor.

Using the context below, answer the student's question clearly and helpfully.
When the question is about SQL or database syntax, include a short SQL code
example formatted in a fenced code block (```sql ... ```). When comparing
multiple things (e.g. JOIN types, normal forms, keys), use a markdown table.
Keep prose explanation concise, then follow with the code/table where useful.

CONTEXT:
{context}

CONVERSATION HISTORY:
{history or "(No earlier messages in this chat.)"}

QUESTION: {query}

Answer using markdown formatting (code blocks, tables) where it aids clarity.
"""

        answer = None
        try:
            if not self.groq_api_key:
                raise RuntimeError("GROQ_API_KEY not set")
            answer = self._call_openai_style(
                self.groq_url, self.groq_api_key, self.groq_model, prompt
            )
            logger.info("Groq generated a response")
        except Exception:
            logger.exception("Groq provider request failed; trying OpenRouter")
            try:
                if not self.openrouter_api_key:
                    raise RuntimeError("OPENROUTER_API_KEY not set")
                answer = self._call_openai_style(
                    self.openrouter_url,
                    self.openrouter_api_key,
                    self.openrouter_model,
                    prompt,
                )
                logger.info("OpenRouter generated a response")
            except Exception:
                logger.exception("OpenRouter provider request failed")

        if not answer:
            answer = f"Based on {', '.join(doc.title for doc in context_docs)}: {query}"

        return {
            "answer": answer.strip(),
            "confidence": 0.88,
            "sources": [doc.title for doc in context_docs],
        }


rag_engine = RAGEngine()
