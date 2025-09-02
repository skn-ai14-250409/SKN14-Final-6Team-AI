"""
qook_chatbot URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.chat.views import LandingView, ChatView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # 메인 페이지
    path('', LandingView.as_view(), name='landing'),
    path('chat/', ChatView.as_view(), name='chat'),
    
    # API
    path('api/', include('apps.api.urls')),
    
    # 앱별 URL
    path('chat/', include('apps.chat.urls')),
]

# 정적 파일 서빙 (개발용)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)