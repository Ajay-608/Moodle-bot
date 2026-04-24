from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import json

@login_required
def rag_search(request):
    if request.method == 'POST':
        query = request.POST.get('query')
        # RAG logic here
        return JsonResponse({'response': 'AI Answer', 'confidence': 0.88})
    return render(request, 'rag/search.html')

@login_required
def build_index(request):
    return render(request, 'rag/index.html')
