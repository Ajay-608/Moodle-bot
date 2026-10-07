import numpy as np
import re
import os
import requests
from sentence_transformers import SentenceTransformer
import faiss
from django.conf import settings
from knowledge.models import Document


class RAGEngine:
    def __init__(self):
        self.initialization_error = None
        self.model = None
        self.index = None
        try:
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            self.dimension = 384

            # --- Groq (primary) ---
            self.groq_url = "https://api.groq.com/openai/v1/chat/completions"
            self.groq_api_key = os.environ.get("GROQ_API_KEY")
            self.groq_model = os.environ.get("LLM_MODEL", "llama-3.1-8b-instant")

            # --- OpenRouter (fallback, used only if Groq fails) ---
            self.openrouter_url = "https://openrouter.ai/api/v1/chat/completions"
            self.openrouter_api_key = os.environ.get("OPENROUTER_API_KEY")
            self.openrouter_model = os.environ.get(
                "OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free"
            )

            print("🔄 Initializing RAG Engine...")
            self._safe_setup()
            print("✅ RAG Engine ready!")
        except Exception as e:
            self.initialization_error = e
            print(f"⚠️ RAG setup failed: {e}")

    def _safe_setup(self):
        index_path = settings.FAISS_INDEX_PATH
        if not os.path.isfile(index_path):
            raise FileNotFoundError(
                f"FAISS index not found at {index_path}. Build it from the "
                "active PostgreSQL Documents with 'python build_index.py'."
            )

        loaded_index = faiss.read_index(str(index_path))
        if not isinstance(loaded_index, faiss.IndexIDMap2):
            raise RuntimeError(
                "The FAISS index does not contain Document primary-key IDs; "
                "rebuild it with build_index.py."
            )
        if loaded_index.d != self.dimension or loaded_index.ntotal == 0:
            raise RuntimeError(
                "The FAISS index is empty or has an unexpected embedding "
                "dimension; rebuild it with build_index.py."
            )
        self.index = loaded_index
        print(f"✅ Loaded FAISS index with Document primary-key IDs from {index_path}")

    def clean_text(self, text):
        text = re.sub(r'#+\s*', '', text)
        text = re.sub(r'\*+', '', text)
        text = re.sub(r'-\s+', '', text)
        text = re.sub(r'\n+', ' ', text)
        return text.strip()

    def search(self, query, k=3):
        if not self.model:
            raise RuntimeError(
                "RAG embedding model is unavailable; check the service logs."
            ) from self.initialization_error
        if not self.index:
            try:
                self._safe_setup()
            except Exception as error:
                self.initialization_error = error
                raise RuntimeError(
                    "FAISS index is unavailable; build it from PostgreSQL "
                    "Documents with 'python build_index.py'."
                ) from error
            self.initialization_error = None
        try:
            query_embedding = self.model.encode(
                [query],
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
            distances, indices = self.index.search(query_embedding.astype('float32'), k)
            document_ids = [int(pk) for pk in indices[0] if pk >= 0]
            documents_by_id = Document.objects.in_bulk(document_ids)
            docs = [documents_by_id[pk] for pk in document_ids if pk in documents_by_id]
            print(f"📄 Context docs found: {len(docs)}")
            return docs, distances[0].tolist()
        except Exception as e:
            print(f"Search error: {e}")
            return [], [1.0] * k

    def _call_openai_style(self, url, api_key, model, prompt, timeout=30, max_tokens=150):
        """Shared caller for Groq and OpenRouter — both use the OpenAI chat format."""
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.1
            },
            timeout=timeout
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        if not content:
            raise RuntimeError(f"Provider returned empty content (model: {model})")
        return content.strip()

    def generate_response(self, query, context_docs):
        print(f"📄 Context docs received: {len(context_docs)}")

        if not context_docs:
            print("⚠️ No docs found — returning fallback")
            return {
                "answer": "Database Systems course covers SQL, JOINs, and normalization. Try asking: 'Explain SQL JOINs' or 'What is 3NF?'",
                "confidence": 0.85,
                "sources": ["CS401 Course"]
            }

        context = "\n\n---\n\n".join([
            f"{doc.title}\n{self.clean_text(doc.content[:200])}"
            for doc in context_docs[:3] if doc.content
        ])

        prompt = f"""You are MoodleBot, a friendly database systems tutor.

Using the context below, answer the student's question clearly and helpfully.
When the question is about SQL or database syntax, include a short SQL code
example formatted in a fenced code block (```sql ... ```). When comparing
multiple things (e.g. JOIN types, normal forms, keys), use a markdown table.
Keep prose explanation concise, then follow with the code/table where useful.

CONTEXT:
{context}

QUESTION: {query}

Answer using markdown formatting (code blocks, tables) where it aids clarity."""

        answer = None

        # --- Try Groq first ---
        try:
            if not self.groq_api_key:
                raise RuntimeError("GROQ_API_KEY not set")
            answer = self._call_openai_style(
                self.groq_url, self.groq_api_key, self.groq_model, prompt, max_tokens=500
            )
            print(f"✅ Groq answered: {answer[:150]}")
        except Exception as e:
            print(f"⚠️ Groq failed ({e}) — trying OpenRouter fallback...")

            # --- Fallback to OpenRouter ---
            try:
                if not self.openrouter_api_key:
                    raise RuntimeError("OPENROUTER_API_KEY not set")
                answer = self._call_openai_style(
                    self.openrouter_url, self.openrouter_api_key,
                    self.openrouter_model, prompt, max_tokens=500
                )
                print(f"✅ OpenRouter answered: {answer[:150]}")
            except Exception as e2:
                print(f"❌ OpenRouter also failed: {e2}")

        if answer:
            answer = answer.strip()
        else:
            # --- Both providers failed: plain-text fallback ---
            titles = [doc.title for doc in context_docs]
            answer = f"Based on {', '.join(titles)}: {query}"

        return {
            "answer": answer,
            "confidence": 0.88,
            "sources": [doc.title for doc in context_docs]
        }


# Global instance
rag_engine = RAGEngine()