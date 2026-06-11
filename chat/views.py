from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db.models import Q
import json
import re

# Safe model imports
try:
    from .models import ChatSession, Message
except ImportError:
    ChatSession = None
    Message = None
    print("⚠️ Chat models unavailable")

# RAG engine import
try:
    from rag_engine import rag_engine
    print("✅ RAG engine loaded in chat views")
except Exception as e:
    rag_engine = None
    print(f"⚠️ RAG unavailable: {e}")

# Safe knowledge base import
try:
    from knowledge.models import Document
except ImportError:
    Document = None
    print("⚠️ Knowledge base unavailable")


@login_required
def chat_view(request):
    """Main chat interface"""
    return render(request, 'chat/chat.html', {
        'title': 'AI Chatbot - MoodleBot'
    })


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def send_message(request):
    try:
        data = json.loads(request.body)
        query = data.get('message', '').strip()
        query_lower = query.lower()

        print(f"🔍 User Query: '{query}'")

        if not query:
            return JsonResponse({'error': 'Empty message'}, status=400)

        # Try Gemini RAG first
        if rag_engine is not None:
            print(f"✅ Using Gemini RAG")
            docs, distances = rag_engine.search(query, k=1)
            result = rag_engine.generate_response(query, docs)
            return JsonResponse({
                'success': True,
                'bot_response': result['answer'],
                'confidence': result['confidence'],
                'sources': result['sources'],
                'source_type': 'gemini_rag'
            })

        # Fallback: keyword-based responses
        print(f"⚙️ Using keyword fallback")
        fallback_responses = {
            'sql': {
                'keywords': ['sql', 'query', 'select', 'insert', 'update', 'delete'],
                'response': 'SQL (Structured Query Language) is used to manage relational databases. Key commands: SELECT (retrieve), INSERT (add), UPDATE (modify), DELETE (remove).',
                'confidence': 0.92
            },
            'join': {
                'keywords': ['join', 'inner', 'left', 'right', 'outer'],
                'response': 'JOINs combine rows from two or more tables. Types: INNER JOIN (matching rows only), LEFT JOIN (all left + matches), RIGHT JOIN (all right + matches), FULL OUTER JOIN (all rows).',
                'confidence': 0.91
            },
            'normalization': {
                'keywords': ['normal', 'normalization', '1nf', '2nf', '3nf', 'bcnf'],
                'response': 'Normalization reduces redundancy. Normal Forms: 1NF (atomic values), 2NF (no partial dependencies), 3NF (no transitive dependencies).',
                'confidence': 0.89
            },
            'key': {
                'keywords': ['key', 'primary', 'foreign', 'unique', 'constraint'],
                'response': 'Database keys maintain data integrity. PRIMARY KEY: unique identifier. FOREIGN KEY: references another table. UNIQUE KEY: ensures uniqueness.',
                'confidence': 0.90
            },
            'index': {
                'keywords': ['index', 'performance', 'faster', 'lookup', 'optimization'],
                'response': 'Database indexes improve query performance. Benefits: faster SELECT, WHERE filtering, JOINs. Drawback: slower INSERT/UPDATE/DELETE.',
                'confidence': 0.88
            },
            'transaction': {
                'keywords': ['transaction', 'acid', 'commit', 'rollback', 'atomic'],
                'response': 'Transactions are atomic sequences of operations. ACID: Atomicity, Consistency, Isolation, Durability. Use COMMIT to save, ROLLBACK to undo.',
                'confidence': 0.87
            }
        }

        best_match = None
        best_score = 0.50

        for key, response_data in fallback_responses.items():
            match_count = sum(1 for kw in response_data['keywords'] if kw in query_lower)
            score = response_data['confidence'] * (match_count / len(response_data['keywords']))
            if score > best_score:
                best_score = score
                best_match = response_data

        if best_match:
            return JsonResponse({
                'success': True,
                'bot_response': best_match['response'],
                'confidence': best_match['confidence'],
                'sources': ['Database Systems Course'],
                'source_type': 'keyword_match'
            })

        return JsonResponse({
            'success': True,
            'bot_response': 'I can help with SQL, JOINs, normalization, keys, indexes and transactions. Please ask a specific question!',
            'confidence': 0.70,
            'sources': ['Help System'],
            'source_type': 'default'
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def rag_chat_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            query = data.get('message', '').strip()
            docs, distances = rag_engine.search(query) if rag_engine else ([], [])
            result = rag_engine.generate_response(query, docs) if rag_engine else {}
            if result:
                return JsonResponse({
                    'success': True,
                    'answer': result['answer'],
                    'confidence': result['confidence'],
                    'sources': result['sources']
                })
            return JsonResponse({
                'success': False,
                'answer': 'No relevant documents found.',
                'confidence': 0.0
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'POST only'}, status=400)


@login_required
def chat_dashboard(request):
    if ChatSession is None:
        return render(request, 'chat/dashboard.html', {'sessions': []})
    sessions = ChatSession.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'chat/dashboard.html', {
        'sessions': sessions,
        'total_sessions': sessions.count(),
        'total_messages': Message.objects.filter(
            session__user=request.user).count() if Message else 0
    })


@login_required
def session_detail(request, session_id):
    if ChatSession is None:
        return render(request, 'chat/session_detail.html', {
            'session': None, 'error': 'Chat not available'
        })
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
        if request.method == 'POST' and request.POST.get('action') == 'delete':
            session.delete()
            from django.shortcuts import redirect
            return redirect('chat:dashboard')
        return render(request, 'chat/session_detail.html', {'session': session})
    except ChatSession.DoesNotExist:
        return render(request, 'chat/session_detail.html', {
            'session': None, 'error': 'Session not found'
        }, status=404)