from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

import json
import logging

from rag_engine import RAGUnavailableError


logger = logging.getLogger(__name__)


# ============================================================
# MODEL IMPORTS
# ============================================================

try:
    from .models import ChatSession, Message
except ImportError:
    ChatSession = None
    Message = None
    logger.warning("Chat models unavailable")


try:
    from knowledge.models import Document
except ImportError:
    Document = None
    logger.warning("Knowledge base unavailable")


# ============================================================
# LAZY RAG ENGINE LOADING
# ============================================================

_rag_engine = None
_rag_engine_loaded = False


def _get_rag_engine():
    """
    Load the RAG engine only when a chat request needs it.
    """

    global _rag_engine
    global _rag_engine_loaded

    if not _rag_engine_loaded:

        try:
            from rag_engine import rag_engine

            _rag_engine = rag_engine

            logger.info(
                "✅ RAG engine loaded successfully"
            )

        except Exception as e:

            logger.exception(
                "❌ RAG engine could not be initialized: %s",
                e
            )

            _rag_engine = None

        finally:
            _rag_engine_loaded = True

    return _rag_engine


# ============================================================
# CHAT PAGE
# ============================================================

@login_required
def chat_view(request):
    """
    Main MoodleBot chat interface.

    A new ChatSession is created when the user opens the
    chat page without explicitly requesting an existing session.
    """

    return render(
        request,
        "chat/chat.html",
        {
            "title": "AI Chatbot - MoodleBot"
        }
    )


# ============================================================
# SEND MESSAGE
# ============================================================

@csrf_exempt
@require_http_methods(["POST"])
@login_required
def send_message(request):

    try:

        # ----------------------------------------------------
        # Parse request
        # ----------------------------------------------------

        data = json.loads(request.body)

        query = data.get(
            "message",
            ""
        ).strip()

        session_id = data.get(
            "session_id"
        )

        query_lower = query.lower()

        logger.info("Received chat message")

        # ----------------------------------------------------
        # Validate message
        # ----------------------------------------------------

        if not query:

            return JsonResponse(
                {
                    "success": False,
                    "error": "Empty message"
                },
                status=400
            )

        # ----------------------------------------------------
        # Validate chat models
        # ----------------------------------------------------

        if ChatSession is None or Message is None:

            return JsonResponse(
                {
                    "success": False,
                    "error": "Chat system is unavailable."
                },
                status=503
            )

        # ----------------------------------------------------
        # Get existing session OR create new session
        # ----------------------------------------------------

        if session_id:

            try:

                session = ChatSession.objects.get(
                    id=session_id,
                    user=request.user
                )

            except ChatSession.DoesNotExist:

                return JsonResponse(
                    {
                        "success": False,
                        "error": "Chat session not found."
                    },
                    status=404
                )

        else:

            session = ChatSession.objects.create(
                user=request.user,
                title=query[:200]
            )

            logger.info("Created ChatSession %s", session.id)

        # ----------------------------------------------------
        # Load previous messages from CURRENT session only
        # ----------------------------------------------------

        previous_messages = (
            Message.objects
            .filter(
                session=session
            )
            .order_by(
                "created_at"
            )
        )

        conversation_history = []

        for message in previous_messages:

            role = (
                "user"
                if message.message_type == "user"
                else "assistant"
            )

            conversation_history.append(
                {
                    "role": role,
                    "content": message.content
                }
            )

        logger.info(
            "Loaded %s previous messages for chat session %s",
            len(conversation_history),
            session.id,
        )

        # ----------------------------------------------------
        # Save current user message
        # ----------------------------------------------------

        Message.objects.create(
            session=session,
            message_type="user",
            content=query
        )

        logger.info("Saved user message to chat session %s", session.id)

        # ====================================================
        # RAG ENGINE
        # ====================================================

        rag_engine = _get_rag_engine()

        if rag_engine is not None:

            logger.info("Using RAG engine")

            # ------------------------------------------------
            # Retrieve top 5 relevant chunks
            # ------------------------------------------------

            docs, scores = rag_engine.search(
                query,
                k=5
            )

            logger.info("Retrieved %s relevant chunks", len(docs))

            # ------------------------------------------------
            # Generate grounded response
            # ------------------------------------------------

            result = rag_engine.generate_response(
                query,
                docs,
                conversation_history=conversation_history
            )

            # ------------------------------------------------
            # Save bot response
            # ------------------------------------------------

            Message.objects.create(
                session=session,
                message_type="bot",
                content=result["answer"],
                confidence_score=result["confidence"]
            )

            logger.info("Saved bot response to chat session %s", session.id)

            return JsonResponse(
                {
                    "success": True,
                    "session_id": session.id,
                    "bot_response": result["answer"],
                    "confidence": result["confidence"],
                    "sources": result["sources"],
                    "source_type": "rag_engine"
                }
            )

        # ====================================================
        # KEYWORD FALLBACK
        # ====================================================

        logger.info("Using keyword fallback")

        fallback_responses = {

            "sql": {
                "keywords": [
                    "sql",
                    "query",
                    "select",
                    "insert",
                    "update",
                    "delete"
                ],

                "response": (
                    "SQL (Structured Query Language) "
                    "is used to manage relational databases. "
                    "Key commands: SELECT (retrieve), "
                    "INSERT (add), UPDATE (modify), "
                    "DELETE (remove)."
                ),

                "confidence": 0.92
            },

            "join": {
                "keywords": [
                    "join",
                    "inner",
                    "left",
                    "right",
                    "outer"
                ],

                "response": (
                    "JOINs combine rows from two or more "
                    "tables. Types: INNER JOIN (matching "
                    "rows only), LEFT JOIN (all left + "
                    "matches), RIGHT JOIN (all right + "
                    "matches), FULL OUTER JOIN "
                    "(all rows)."
                ),

                "confidence": 0.91
            },

            "normalization": {
                "keywords": [
                    "normal",
                    "normalization",
                    "1nf",
                    "2nf",
                    "3nf",
                    "bcnf"
                ],

                "response": (
                    "Normalization reduces redundancy. "
                    "Normal Forms: 1NF (atomic values), "
                    "2NF (no partial dependencies), "
                    "3NF (no transitive dependencies)."
                ),

                "confidence": 0.89
            },

            "key": {
                "keywords": [
                    "key",
                    "primary",
                    "foreign",
                    "unique",
                    "constraint"
                ],

                "response": (
                    "Database keys maintain data integrity. "
                    "PRIMARY KEY: unique identifier. "
                    "FOREIGN KEY: references another table. "
                    "UNIQUE KEY: ensures uniqueness."
                ),

                "confidence": 0.90
            },

            "index": {
                "keywords": [
                    "index",
                    "performance",
                    "faster",
                    "lookup",
                    "optimization"
                ],

                "response": (
                    "Database indexes improve query "
                    "performance. Benefits: faster SELECT, "
                    "WHERE filtering, and JOINs. "
                    "Drawback: slower INSERT/UPDATE/DELETE."
                ),

                "confidence": 0.88
            },

            "transaction": {
                "keywords": [
                    "transaction",
                    "acid",
                    "commit",
                    "rollback",
                    "atomic"
                ],

                "response": (
                    "Transactions are atomic sequences of "
                    "operations. ACID: Atomicity, "
                    "Consistency, Isolation, Durability. "
                    "Use COMMIT to save, ROLLBACK to undo."
                ),

                "confidence": 0.87
            }
        }

        best_match = None
        best_score = 0.50

        for key, response_data in (
            fallback_responses.items()
        ):

            match_count = sum(
                1
                for keyword in response_data["keywords"]
                if keyword in query_lower
            )

            score = (
                response_data["confidence"]
                * (
                    match_count
                    / len(response_data["keywords"])
                )
            )

            if score > best_score:

                best_score = score
                best_match = response_data

        # ----------------------------------------------------
        # Matching fallback
        # ----------------------------------------------------

        if best_match:

            answer = best_match["response"]
            confidence = best_match["confidence"]

            Message.objects.create(
                session=session,
                message_type="bot",
                content=answer,
                confidence_score=confidence
            )

            return JsonResponse(
                {
                    "success": True,
                    "session_id": session.id,
                    "bot_response": answer,
                    "confidence": confidence,
                    "sources": [
                        "Database Systems Course"
                    ],
                    "source_type": "keyword_match"
                }
            )

        # ----------------------------------------------------
        # Default fallback
        # ----------------------------------------------------

        answer = (
            "I can help with SQL, JOINs, "
            "normalization, keys, indexes "
            "and transactions. Please ask "
            "a specific question!"
        )

        confidence = 0.70

        Message.objects.create(
            session=session,
            message_type="bot",
            content=answer,
            confidence_score=confidence
        )

        return JsonResponse(
            {
                "success": True,
                "session_id": session.id,
                "bot_response": answer,
                "confidence": confidence,
                "sources": ["Help System"],
                "source_type": "default"
            }
        )

    except json.JSONDecodeError:

        return JsonResponse(
            {
                "success": False,
                "error": "Invalid JSON"
            },
            status=400
        )

    except RAGUnavailableError as e:
        logger.exception("RAG is unavailable while processing chat message")
        return JsonResponse(
            {
                "success": False,
                "error": str(e),
            },
            status=503,
        )

    except Exception as e:

        logger.exception(
            "❌ Error while processing chat message: %s",
            e
        )

        return JsonResponse(
            {
                "success": False,
                "error": str(e)
            },
            status=500
        )


# ============================================================
# RAG CHAT API
# ============================================================

@login_required
def rag_chat_api(request):

    if request.method != "POST":

        return JsonResponse(
            {
                "error": "POST only"
            },
            status=400
        )

    try:

        data = json.loads(
            request.body
        )

        query = data.get(
            "message",
            ""
        ).strip()

        if not query:

            return JsonResponse(
                {
                    "success": False,
                    "answer": "Empty message.",
                    "confidence": 0.0
                },
                status=400
            )

        rag_engine = _get_rag_engine()

        # ----------------------------------------------------
        # RAG unavailable
        # ----------------------------------------------------

        if rag_engine is None:

            return JsonResponse(
                {
                    "success": False,
                    "answer": (
                        "The RAG engine is currently "
                        "unavailable."
                    ),
                    "confidence": 0.0,
                    "sources": []
                },
                status=503
            )

        # ----------------------------------------------------
        # Retrieve top 5 chunks
        # ----------------------------------------------------

        docs, scores = rag_engine.search(
            query,
            k=5
        )

        # ----------------------------------------------------
        # Generate response
        # ----------------------------------------------------

        result = rag_engine.generate_response(
            query,
            docs
        )

        return JsonResponse(
            {
                "success": True,
                "answer": result["answer"],
                "confidence": result["confidence"],
                "sources": result["sources"]
            }
        )

    except json.JSONDecodeError:

        return JsonResponse(
            {
                "error": "Invalid JSON"
            },
            status=400
        )

    except RAGUnavailableError as e:
        logger.exception("RAG is unavailable in the RAG chat API")
        return JsonResponse(
            {
                "success": False,
                "error": str(e),
            },
            status=503,
        )

    except Exception as e:

        logger.exception(
            "❌ RAG API error: %s",
            e
        )

        return JsonResponse(
            {
                "error": str(e)
            },
            status=500
        )


# ============================================================
# CHAT DASHBOARD
# ============================================================

@login_required
def chat_dashboard(request):

    if ChatSession is None:

        return render(
            request,
            "chat/dashboard.html",
            {
                "sessions": []
            }
        )

    sessions = (
        ChatSession.objects
        .filter(
            user=request.user
        )
        .order_by(
            "-created_at"
        )
    )

    total_messages = 0

    if Message:

        total_messages = (
            Message.objects
            .filter(
                session__user=request.user
            )
            .count()
        )

    return render(
        request,
        "chat/dashboard.html",
        {
            "sessions": sessions,
            "total_sessions": sessions.count(),
            "total_messages": total_messages
        }
    )


# ============================================================
# SESSION DETAIL
# ============================================================

@login_required
def session_detail(
    request,
    session_id
):

    if ChatSession is None:

        return render(
            request,
            "chat/session_detail.html",
            {
                "session": None,
                "error": "Chat not available"
            }
        )

    try:

        session = (
            ChatSession.objects.get(
                id=session_id,
                user=request.user
            )
        )

        # ----------------------------------------------------
        # Delete session
        # ----------------------------------------------------

        if (
            request.method == "POST"
            and request.POST.get("action") == "delete"
        ):

            session.delete()

            return redirect(
                "chat:dashboard"
            )

        return render(
            request,
            "chat/session_detail.html",
            {
                "session": session
            }
        )

    except ChatSession.DoesNotExist:

        return render(
            request,
            "chat/session_detail.html",
            {
                "session": None,
                "error": "Session not found"
            },
            status=404
        )