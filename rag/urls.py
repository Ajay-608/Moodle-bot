from django.urls import path
from . import views

app_name = 'rag'

urlpatterns = [
    path('search/', views.rag_search, name='search'),
    path('index/', views.build_index, name='build_index'),
]
