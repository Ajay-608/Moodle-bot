from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Count, Avg  # ✅ FIXED import
from chat.models import Message, ChatSession
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

@login_required
def teacher_analytics(request):
    stats = {
        'total_sessions': ChatSession.objects.count(),
        'user_questions': Message.objects.filter(message_type='user').count(),
        'bot_responses': Message.objects.filter(message_type='bot').count(),
        'avg_accuracy': Message.objects.filter(
            message_type='bot', confidence_score__isnull=False
        ).aggregate(avg=Avg('confidence_score'))['avg'] or 0.88,
        'top_keywords': ['SQL', 'JOIN', 'normalization', 'primary key', 'index']
    }
    return render(request, 'analytics/teacher.html', {'stats': stats})

@login_required
def analytics_dashboard(request):
    return render(request, 'analytics/dashboard.html')
