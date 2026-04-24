from django.urls import path
from . import views

app_name = 'knowledge'

urlpatterns = [
    path('', views.knowledge_dashboard, name='dashboard'),
    path('upload/', views.upload_document, name='upload'),
    path('documents/', views.document_list, name='documents'),
    path('faq/', views.faq_list, name='faq'),
]
