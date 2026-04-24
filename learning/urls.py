from django.urls import path
from . import views

app_name = 'learning'

urlpatterns = [
    path('', views.learning_dashboard, name='dashboard'),
    path('progress/', views.progress_tracker, name='progress'),
    path('resources/', views.learning_resources, name='resources'),
]
