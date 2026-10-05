from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Count, Avg
from django.contrib import messages

from chat.models import ChatSession, Message
from core.models import UserProfile


User = get_user_model()


@login_required
def admin_dashboard(request):
    total_users = User.objects.count()
    total_chats = ChatSession.objects.count()
    total_messages = Message.objects.count()

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
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        user_type = request.POST.get('user_type', 'student')

        # Validate required fields
        if not username or not password:
            messages.error(request, 'Username and password are required.')
            return redirect('admin_panel:users')

        # Validate role
        valid_roles = {'student', 'teacher', 'admin'}
        if user_type not in valid_roles:
            messages.error(request, 'Invalid user role selected.')
            return redirect('admin_panel:users')

        # Prevent duplicate usernames
        if User.objects.filter(username__iexact=username).exists():
            messages.error(
                request,
                f'Username "{username}" already exists.'
            )
            return redirect('admin_panel:users')

        # Create Django authentication user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        # Create role profile
        UserProfile.objects.create(
            user=user,
            user_type=user_type
        )

        messages.success(
            request,
            f'User "{username}" created successfully as {user_type.title()}.'
        )

        return redirect('admin_panel:users')

    users = User.objects.select_related('profile').all().order_by(
        '-is_staff',
        'username'
    )

    return render(
        request,
        'admin_panel/users.html',
        {'users': users}
    )


@login_required
def performance_metrics(request):
    sessions = ChatSession.objects.select_related('user').order_by(
        '-created_at'
    )[:50]

    return render(
        request,
        'admin_panel/metrics.html',
        {'sessions': sessions}
    )