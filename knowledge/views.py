from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Document
import os

@login_required
def knowledge_dashboard(request):
    """Knowledge base dashboard"""
    total_docs = Document.objects.filter(course_id=1).count()
    context = {
        'total_docs': total_docs,
        'recent_docs': Document.objects.filter(course_id=1).order_by('-created_at')[:5]
    }
    return render(request, 'knowledge/dashboard.html', context)

@login_required
def upload_document(request):
    """Upload document form"""
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        course_id = 1  # CS401
        
        if title and content:
            Document.objects.create(
                title=title,
                content=content,
                course_id=course_id
            )
            messages.success(request, f'✅ Document "{title}" uploaded successfully!')
            return render(request, 'knowledge/upload.html', {'success': True})
        else:
            messages.error(request, '❌ Title and content required!')
    
    return render(request, 'knowledge/upload.html')

@login_required
def document_list(request):
    """List all documents"""
    documents = Document.objects.filter(course_id=1).order_by('-created_at')
    return render(request, 'knowledge/documents.html', {'documents': documents})

@login_required
def faq_list(request):
    """FAQ page for Database Systems"""
    faqs = [
        {'q': 'What is SQL?', 'a': 'Structured Query Language for managing relational databases.'},
        {'q': 'What are JOINs?', 'a': 'Combine rows from two or more tables based on related columns.'},
        {'q': 'What is Normalization?', 'a': 'Process to organize data to reduce redundancy.'},
    ]
    return render(request, 'knowledge/faq.html', {'faqs': faqs})
