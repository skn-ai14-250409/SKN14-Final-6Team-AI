"""
API URL 설정
"""
from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    path('health/', views.HealthCheckView.as_view(), name='health'),
    path('chat/', views.ChatAPIView.as_view(), name='chat'),
    path('sessions/<uuid:session_id>/', views.SessionAPIView.as_view(), name='session'),
    path('stats/', views.StatsAPIView.as_view(), name='stats'),
]