from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import timedelta

from knowledge.models import Document
from chat.models import ChatSession, Message
from .models import UserProfile, ResponseFeedback, LearningGap, TAMSurvey

User = get_user_model()

# 🔓 PUBLIC VIEWS (No login required)
@csrf_protect
def register(request):
    """User registration with role selection"""
    from django import forms
    
    class RoleUserCreationForm(UserCreationForm):
        user_type = forms.ChoiceField(
            choices=[
                ('student', '📚 Student - Learn & Access Chat'),
                ('teacher', '👨‍🏫 Teacher - Create Courses & Manage'),
                ('admin', '🔧 Admin - Full System Access'),
            ],
            widget=forms.RadioSelect,
            required=True
        )
        
        class Meta:
            model = User
            fields = ('username', 'password1', 'password2', 'user_type')
    
    if request.method == 'POST':
        form = RoleUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            user_type = form.cleaned_data.get('user_type', 'student')
            # Create UserProfile with selected role
            UserProfile.objects.get_or_create(user=user, defaults={'user_type': user_type})
            username = form.cleaned_data.get('username')
            messages.success(request, f'🎉 Account created as {user_type.upper()}! Please login.')
            return redirect('core:login')
        else:
            messages.error(request, '❌ Registration failed. Fix errors below.')
    else:
        form = RoleUserCreationForm()
    return render(request, 'core/register.html', {'form': form})

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔓 ROLE-BASED LOGIN PAGES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@csrf_protect
def student_login(request):
    """Student-specific login page"""
    from django.contrib.auth import authenticate, login
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            profile = UserProfile.objects.get_or_create(user=user)[0]
            if profile.user_type != 'student':
                messages.error(request, '❌ This account is not a student account. Use the correct login.')
                return redirect('core:student_login')
            login(request, user)
            return redirect('core:dashboard')
        else:
            messages.error(request, '❌ Invalid credentials')
    
    return render(request, 'core/login_student.html')

@csrf_protect
def teacher_login(request):
    """Teacher-specific login page"""
    from django.contrib.auth import authenticate, login
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            profile = UserProfile.objects.get_or_create(user=user)[0]
            if profile.user_type != 'teacher':
                messages.error(request, '❌ This account is not a teacher account. Use the correct login.')
                return redirect('core:teacher_login')
            login(request, user)
            return redirect('core:dashboard')
        else:
            messages.error(request, '❌ Invalid credentials')
    
    return render(request, 'core/login_teacher.html')

@csrf_protect
def admin_login(request):
    """Admin-specific login page"""
    from django.contrib.auth import authenticate, login
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            profile = UserProfile.objects.get_or_create(user=user)[0]
            if profile.user_type != 'admin':
                messages.error(request, '❌ This account is not an admin account. Use the correct login.')
                return redirect('core:admin_login')
            login(request, user)
            return redirect('core:dashboard')
        else:
            messages.error(request, '❌ Invalid credentials')
    
    return render(request, 'core/login_admin.html')

# 🔐 ROLE-BASED MAIN DASHBOARD
@login_required
def dashboard(request):
    """Route to appropriate dashboard based on user role"""
    profile = UserProfile.objects.get_or_create(user=request.user)[0]
    
    if profile.user_type == 'admin':
        return admin_dashboard(request)
    elif profile.user_type == 'teacher':
        return teacher_dashboard(request)
    else:
        return student_dashboard(request)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📚 STUDENT DASHBOARD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@login_required
def student_dashboard(request):
    """Student-specific dashboard: My chats, FAQs, learning progress"""
    my_sessions = ChatSession.objects.filter(user=request.user).order_by('-created_at')[:5]
    my_messages = Message.objects.filter(session__user=request.user).count()
    
    # Learning gaps for this student
    learning_gaps = LearningGap.objects.filter(user=request.user).order_by('-incorrect_attempts')[:3]
    
    # Feedback I've given
    my_feedback = ResponseFeedback.objects.filter(user=request.user).count()
    
    # Average confidence of responses to me
    avg_confidence = Message.objects.filter(
        message_type='bot',
        session__user=request.user,
        confidence_score__isnull=False
    ).aggregate(avg=Avg('confidence_score'))['avg'] or 0.88
    
    context = {
        'page_title': '📚 My Learning Dashboard',
        'my_sessions': my_sessions,
        'my_messages': my_messages,
        'learning_gaps': learning_gaps,
        'my_feedback': my_feedback,
        'avg_confidence': round(avg_confidence * 100, 1),
        'section': 'student',
    }
    return render(request, 'core/student_dashboard.html', context)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 👨‍🏫 TEACHER DASHBOARD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@login_required
def teacher_dashboard(request):
    """Teacher-specific dashboard: Class analytics, struggling students, content gaps"""
    # Ensure user is teacher/admin
    profile = UserProfile.objects.get_or_create(user=request.user)[0]
    if profile.user_type not in ['teacher', 'admin']:
        return redirect('core:student_dashboard')
    
    # Class statistics
    total_students = User.objects.filter(profile__user_type='student').count()
    total_sessions = ChatSession.objects.count()
    total_questions = Message.objects.filter(message_type='user').count()
    total_responses = Message.objects.filter(message_type='bot').count()
    
    # Top questions this week
    week_ago = timezone.now() - timedelta(days=7)
    user_messages = Message.objects.filter(
        message_type='user',
        created_at__gte=week_ago
    ).values('content').annotate(count=Count('id')).order_by('-count')[:5]
    
    # Struggling students (most learning gaps)
    struggling = LearningGap.objects.values('user__username', 'user_id').annotate(
        gap_count=Count('id'),
        avg_attempts=Avg('incorrect_attempts')
    ).order_by('-gap_count')[:5]
    
    # Low-rated responses
    low_rated = ResponseFeedback.objects.filter(
        rating__lt=3
    ).select_related('message', 'user').order_by('-created_at')[:5]
    
    # Accuracy trend (this week)
    avg_accuracy = Message.objects.filter(
        message_type='bot',
        confidence_score__isnull=False,
        created_at__gte=week_ago
    ).aggregate(avg=Avg('confidence_score'))['avg'] or 0.88
    
    context = {
        'page_title': '👨‍🏫 Teacher Dashboard',
        'total_students': total_students,
        'total_sessions': total_sessions,
        'total_questions': total_questions,
        'total_responses': total_responses,
        'user_messages': user_messages,
        'struggling': struggling,
        'low_rated': low_rated,
        'avg_accuracy': round(avg_accuracy * 100, 1),
        'section': 'teacher',
    }
    return render(request, 'core/teacher_dashboard.html', context)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔧 ADMIN DASHBOARD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@login_required
def admin_dashboard(request):
    """Admin-specific dashboard: System config, user management, performance"""
    # Ensure user is admin
    profile = UserProfile.objects.get_or_create(user=request.user)[0]
    if profile.user_type != 'admin':
        return redirect('core:teacher_dashboard')
    
    # User statistics
    total_users = User.objects.count()
    students = User.objects.filter(profile__user_type='student').count()
    teachers = User.objects.filter(profile__user_type='teacher').count()
    admins = User.objects.filter(profile__user_type='admin').count()
    
    # System statistics
    total_sessions = ChatSession.objects.count()
    total_messages = Message.objects.count()
    total_docs = Document.objects.count()
    total_feedback = ResponseFeedback.objects.count()
    
    # Performance metrics
    avg_accuracy = Message.objects.filter(
        message_type='bot',
        confidence_score__isnull=False
    ).aggregate(avg=Avg('confidence_score'))['avg'] or 0.88
    
    # TAM survey summary
    tam_surveys = TAMSurvey.objects.count()
    tam_avg = TAMSurvey.objects.aggregate(
        pu=Avg('pu_score'),
        eou=Avg('eou_score'),
        attitude=Avg('attitude_score'),
        intention=Avg('intention_score')
    )
    
    # Recent low-rated responses
    low_rated = ResponseFeedback.objects.filter(
        rating__lt=3
    ).select_related('message', 'user').order_by('-created_at')[:5]
    
    # Knowledge base status
    recent_docs = Document.objects.order_by('-created_at')[:5]
    
    # Active sessions (today)
    today = timezone.now().date()
    today_sessions = ChatSession.objects.filter(created_at__date=today).count()
    today_messages = Message.objects.filter(created_at__date=today).count()
    
    context = {
        'page_title': '🔧 Admin Dashboard',
        'total_users': total_users,
        'students': students,
        'teachers': teachers,
        'admins': admins,
        'total_sessions': total_sessions,
        'total_messages': total_messages,
        'total_docs': total_docs,
        'total_feedback': total_feedback,
        'avg_accuracy': round(avg_accuracy * 100, 1),
        'tam_surveys': tam_surveys,
        'tam_avg': tam_avg,
        'low_rated': low_rated,
        'recent_docs': recent_docs,
        'today_sessions': today_sessions,
        'today_messages': today_messages,
        'section': 'admin',
    }
    return render(request, 'core/admin_dashboard.html', context)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LEGACY/SUPPORT VIEWS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@login_required
def course_list(request):
    """Course list for teachers/admins"""
    courses = [
        {'id': 1, 'name': 'CS401 Databases', 'docs': 15},
        {'id': 2, 'name': 'CS402 Info Systems', 'docs': 8},
    ]
    return render(request, 'core/course_list.html', {'courses': courses})

@login_required
def profile(request):
    """User profile page"""
    profile = UserProfile.objects.get_or_create(user=request.user)[0]
    context = {
        'user': request.user,
        'user_profile': profile,
        'user_type': profile.user_type
    }
    return render(request, 'core/profile.html', context)

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
        course_id = 1
        
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
