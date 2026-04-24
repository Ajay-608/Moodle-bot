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

# Safe RAG import - DISABLED due to heavy TensorFlow dependencies
# Comment back in when RAG is needed for semantic search
# try:
#     from rag_engine import rag_engine
# except Exception as e:
#     rag_engine = None
#     print(f"⚠️ RAG unavailable: {type(e).__name__}")
rag_engine = None  # Not used in current implementation

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

def search_knowledge_base(query):
    """
    Search knowledge base for relevant documents
    Uses improved keyword matching and relevance scoring
    Returns: (answer, confidence, sources)
    """
    if Document is None:
        return None, 0.0, []
    
    query_lower = query.lower()
    
    # Extract keywords from query
    keywords = re.findall(r'\b\w+\b', query_lower)
    keywords = [k for k in keywords if len(k) > 2]  # Filter short words
    
    if not keywords:
        return None, 0.0, []
    
    # Get all documents from knowledge base
    all_docs = Document.objects.filter(course_id=1)
    
    # Score each document based on keyword matches
    scored_docs = []
    
    for doc in all_docs:
        doc_content_lower = (doc.title + ' ' + doc.content).lower()
        
        # Count keyword matches
        match_count = 0
        for keyword in keywords:
            # Check if keyword appears in document
            if keyword in doc_content_lower:
                match_count += 1
        
        # Calculate relevance score
        if match_count > 0:
            # Score based on percentage of keywords matched
            relevance = match_count / len(keywords)
            
            # Boost score for matches in title
            if keyword in doc.title.lower():
                relevance += 0.2
            
            scored_docs.append((doc, relevance, match_count))
    
    if not scored_docs:
        return None, 0.0, []
    
    # Sort by relevance score (highest first)
    scored_docs.sort(key=lambda x: x[1], reverse=True)
    
    # Get best match
    best_doc, relevance_score, match_count = scored_docs[0]
    
    # Calculate confidence (0.70 to 0.95)
    confidence = min(0.95, 0.70 + (relevance_score * 0.25))
    
    # Extract content
    content = best_doc.content
    sources = [best_doc.title]
    
    return content, confidence, sources

@csrf_exempt
@require_http_methods(["POST"])
@login_required
def send_message(request):
    """
    IMPROVED CHATBOT - Uses knowledge base to respond to queries
    Returns relevant answers from database with confidence scores
    """
    try:
        data = json.loads(request.body)
        query = data.get('message', '').strip()
        query_lower = query.lower()
        
        print(f"🔍 User Query: '{query}'")
        
        if not query:
            return JsonResponse({'error': 'Empty message'}, status=400)
        
        # Try knowledge base search first
        answer, confidence, sources = search_knowledge_base(query)
        
        if answer and confidence > 0.60:
            print(f"✅ KB Match: [{confidence*100:.1f}%] Found in knowledge base")
            # Clean up the answer
            answer = answer.replace('\\n', '\n').strip()
            # Limit length
            if len(answer) > 1000:
                answer = answer[:1000] + "..."
            
            return JsonResponse({
                'success': True,
                'bot_response': answer,
                'confidence': confidence,
                'sources': sources,
                'source_type': 'knowledge_base'
            })
        
        # Fallback: keyword-based intelligent responses
        print(f"⚙️  Using intelligent keyword matching")
        
        fallback_responses = {
            'sql': {
                'keywords': ['sql', 'query', 'select', 'insert', 'update', 'delete'],
                'response': 'SQL (Structured Query Language) is used to manage relational databases. Key commands: SELECT (retrieve data), INSERT (add data), UPDATE (modify data), DELETE (remove data), CREATE (create tables), ALTER (modify tables), DROP (delete tables). SQL operations are typically categorized as DDL (Data Definition Language) or DML (Data Manipulation Language).',
                'confidence': 0.92
            },
            'join': {
                'keywords': ['join', 'inner', 'left', 'right', 'outer', 'inner join', 'left join'],
                'response': 'JOINs combine rows from two or more tables. Types: INNER JOIN (matching rows only), LEFT JOIN (all left + matches), RIGHT JOIN (all right + matches), FULL OUTER JOIN (all rows), CROSS JOIN (Cartesian product). JOINs are essential for querying related data across multiple tables.',
                'confidence': 0.91
            },
            'normalization': {
                'keywords': ['normal', 'normalization', '1nf', '2nf', '3nf', 'redundancy', 'bcnf'],
                'response': 'Normalization organizes database structure to reduce redundancy. Normal Forms: 1NF (Atomic values), 2NF (No partial dependencies), 3NF (No transitive dependencies), BCNF, 4NF, 5NF. Most databases normalize to 3NF. Normalization improves data integrity and reduces storage, but may require more JOINs for queries.',
                'confidence': 0.89
            },
            'key': {
                'keywords': ['key', 'primary', 'foreign', 'unique', 'constraint', 'integrity'],
                'response': 'Database keys maintain data integrity. PRIMARY KEY: unique identifier (NOT NULL + UNIQUE), one per table. FOREIGN KEY: references another table\'s primary key, maintains relationships. UNIQUE KEY: ensures uniqueness but allows NULL. Keys enable fast lookups and prevent duplicate/orphaned records.',
                'confidence': 0.90
            },
            'index': {
                'keywords': ['index', 'performance', 'faster', 'lookup', 'search', 'optimization'],
                'response': 'Database indexes improve query performance by creating sorted lookup structures. Benefits: faster SELECT, WHERE filtering, JOINs. Types: Primary Key Index, Unique Index, Composite Index, Full-text Index. Drawbacks: slower INSERT/UPDATE/DELETE, extra disk space. Index frequently searched columns for significant performance gains.',
                'confidence': 0.88
            },
            'transaction': {
                'keywords': ['transaction', 'acid', 'commit', 'rollback', 'atomic', 'isolated'],
                'response': 'Transactions are atomic sequences of database operations (all succeed or all fail). ACID properties: Atomicity (all-or-nothing), Consistency (valid state), Isolation (independent), Durability (persisted). Usage: BEGIN, execute statements, COMMIT (save) or ROLLBACK (undo). Critical for data integrity in multi-step operations.',
                'confidence': 0.87
            }
        }
        
        # Match keywords to find best response
        best_match = None
        best_score = 0.50
        
        for key, response_data in fallback_responses.items():
            match_count = sum(1 for kw in response_data['keywords'] if kw in query_lower)
            score = response_data['confidence'] * (match_count / len(response_data['keywords']))
            
            if score > best_score:
                best_score = score
                best_match = response_data
        
        if best_match:
            answer = best_match['response']
            confidence = min(0.93, best_match['confidence'])
            sources = ['Database Systems Course']
            
            print(f"✅ Keyword Match: [{confidence*100:.1f}%] Response generated")
            
            return JsonResponse({
                'success': True,
                'bot_response': answer,
                'confidence': confidence,
                'sources': sources,
                'source_type': 'keyword_match'
            })
        
        # Default response
        default_response = 'I can help with SQL, JOINs, normalization, keys, indexes, transactions, and other database concepts. Please ask a specific question about databases and I\'ll provide detailed information with examples.'
        
        return JsonResponse({
            'success': True,
            'bot_response': default_response,
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
    """RAG backup endpoint - uses loaded knowledge base"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            query = data.get('message', '').strip()
            
            answer, confidence, sources = search_knowledge_base(query)
            
            if answer:
                return JsonResponse({
                    'success': True,
                    'answer': answer,
                    'confidence': confidence,
                    'sources': sources
                })
            else:
                return JsonResponse({
                    'success': False,
                    'answer': 'No relevant documents found in knowledge base.',
                    'confidence': 0.0
                })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'POST only'}, status=400)

@login_required
def chat_dashboard(request):
    """View all chat sessions for the logged-in user"""
    if ChatSession is None:
        return render(request, 'chat/dashboard.html', {'sessions': []})
    
    sessions = ChatSession.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'chat/dashboard.html', {
        'sessions': sessions,
        'total_sessions': sessions.count(),
        'total_messages': Message.objects.filter(session__user=request.user).count() if Message else 0
    })

@login_required
def session_detail(request, session_id):
    """View a specific chat session with all messages"""
    if ChatSession is None:
        return render(request, 'chat/session_detail.html', {'session': None, 'error': 'Chat not available'})
    
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
        
        # Handle delete action
        if request.method == 'POST' and request.POST.get('action') == 'delete':
            session.delete()
            from django.shortcuts import redirect
            return redirect('chat:dashboard')
        
        return render(request, 'chat/session_detail.html', {
            'session': session
        })
    except ChatSession.DoesNotExist:
        return render(request, 'chat/session_detail.html', {
            'session': None,
            'error': 'Session not found'
        }, status=404)