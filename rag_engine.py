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
        try:
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            self.dimension = 384
            self.index = None

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
            print(f"⚠️ RAG setup failed: {e}")
            self.model = None
            self.index = None

    def _safe_setup(self):
        index_path = 'rag_index.faiss'
        if os.path.exists(index_path):
            try:
                self.index = faiss.read_index(index_path)
                print("✅ Loaded FAISS index")
                return
            except:
                pass
        self.index = faiss.IndexFlatL2(self.dimension)
        print("✅ Created empty FAISS index")

    def clean_text(self, text):
        text = re.sub(r'#+\s*', '', text)
        text = re.sub(r'\*+', '', text)
        text = re.sub(r'-\s+', '', text)
        text = re.sub(r'\n+', ' ', text)
        return text.strip()

    def search(self, query, k=3):
        if not self.model or not self.index:
            return [], [1.0] * k
        try:
            query_embedding = self.model.encode([query])
            distances, indices = self.index.search(query_embedding.astype('float32'), k)
            all_docs = list(Document.objects.all().order_by('id'))
            docs = []
            for idx in indices[0]:
                try:
                    if 0 <= idx < len(all_docs):
                        docs.append(all_docs[idx])
                except:
                    continue
            print(f"📄 Context docs found: {len(docs)}")
            return docs, distances[0].tolist()
        except Exception as e:
            print(f"Search error: {e}")
            return [], [1.0] * k

    def _call_openai_style(self, url, api_key, model, prompt, timeout=30):
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
                "max_tokens": 150,
                "temperature": 0.1
            },
            timeout=timeout
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

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

Using the context below, answer the student's question in a natural
conversational way. Do NOT use markdown headers, bullet symbols, or
hashtags. Just write 2-3 plain sentences like a teacher explaining
to a student.

CONTEXT:
{context}

QUESTION: {query}

Answer in plain conversational sentences only."""

        answer = None

        # --- Try Groq first ---
        try:
            if not self.groq_api_key:
                raise RuntimeError("GROQ_API_KEY not set")
            answer = self._call_openai_style(
                self.groq_url, self.groq_api_key, self.groq_model, prompt
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
                    self.openrouter_model, prompt
                )
                print(f"✅ OpenRouter answered: {answer[:150]}")
            except Exception as e2:
                print(f"❌ OpenRouter also failed: {e2}")

        if answer:
            answer = re.sub(r'#+\s*', '', answer)
            answer = re.sub(r'\*\*', '', answer)
            answer = re.sub(r'\n+', ' ', answer).strip()
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