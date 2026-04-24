from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.chat_view, name='chat'),
    path('send/', views.send_message, name='send_message'),
    path('api/rag/', views.rag_chat_api, name='rag_chat_api'),
    path('dashboard/', views.chat_dashboard, name='dashboard'),
    path('session/<int:session_id>/', views.session_detail, name='session_detail'),]