from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Count, Avg  # ✅ FIXED - Added Avg import
from chat.models import ChatSession, Message

User = get_user_model()

@login_required
def admin_dashboard(request):
    total_users = User.objects.count()
    total_chats = ChatSession.objects.count()
    total_messages = Message.objects.count()
    
    # ✅ FIXED Avg calculation
    avg_result = Message.objects.filter(
        message_type='bot', 
        confidence_score__isnull=False
    ).aggregate(avg_acc=Avg('confidence_score'))
    
    avg_accuracy = (avg_result['avg_acc'] or 0.88) * 100
    
    context = {
        'total_users': total_users,
        'total_chats': total_chats,
        'total_messages': total_messages,
        'avg_accuracy': round(avg_accuracy, 1)
    }
    return render(request, 'admin_panel/dashboard.html', context)

@login_required
def user_management(request):
    users = User.objects.all().order_by('-is_staff', 'username')
    return render(request, 'admin_panel/users.html', {'users': users})

@login_required
def performance_metrics(request):
    sessions = ChatSession.objects.select_related('user').order_by('-created_at')[:50]
    return render(request, 'admin_panel/metrics.html', {'sessions': sessions})
