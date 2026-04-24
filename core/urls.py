from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'core'

urlpatterns = [
    # Core dashboard and auth
    path('', views.dashboard, name='dashboard'),
    path('register/', views.register, name='register'),
    
    # Generic login (redirects to dashboard)
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    
    # Role-specific login pages
    path('login/student/', views.student_login, name='student_login'),
    path('login/teacher/', views.teacher_login, name='teacher_login'),
    path('login/admin/', views.admin_login, name='admin_login'),
    
    path('logout/', auth_views.LogoutView.as_view(next_page='core:login'), name='logout'),  # Fixed: use core:login
    
    # Courses (missing from your template)
    path('courses/', views.course_list, name='course_list'),
    
    # Profile (missing from your template)
    path('profile/', views.profile, name='profile'),
    
    # Knowledge routes
    path('knowledge/', views.knowledge_dashboard, name='knowledge_dashboard'),
    path('knowledge/upload/', views.upload_document, name='upload_document'),
    path('knowledge/documents/', views.document_list, name='document_list'),
    path('knowledge/faq/', views.faq_list, name='faq_list'),
]
