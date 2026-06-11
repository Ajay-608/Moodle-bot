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
            self.ollama_url = "http://localhost:11434/api/generate"
            self.ollama_model = "llama3.2:1b"
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

        try:
            response = requests.post(
                self.ollama_url,
                json={


                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {

                        "num_predict": 150,
                        "temperature": 0.1
                    }
                },
                timeout=60
            )
            answer = response.json()["response"].strip()
            print(f"✅ Ollama answered: {answer[:150]}")
            answer = re.sub(r'#+\s*', '', answer)
            answer = re.sub(r'\*\*', '', answer)
            answer = re.sub(r'\n+', ' ', answer).strip()
        except Exception as e:
            print(f"❌ Ollama error: {e}")
            titles = [doc.title for doc in context_docs]
            answer = f"Based on {', '.join(titles)}: {query}"

        return {
            "answer": answer,
            "confidence": 0.88,
            "sources": [doc.title for doc in context_docs]
        }


# Global instance
rag_engine = RAGEngine()