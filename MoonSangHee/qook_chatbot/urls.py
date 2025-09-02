from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("", include(("apps.chat.urls", "chat"), namespace="chat")),   # /, /chat/, /api/chat/
    path("api/", include(("apps.api.urls", "api"), namespace="api")),  # /api/v1/... 권장
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
