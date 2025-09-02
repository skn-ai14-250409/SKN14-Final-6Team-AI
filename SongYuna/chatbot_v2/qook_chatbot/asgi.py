"""
ASGI config for qook_chatbot project.
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qook_chatbot.settings')

django_asgi_app = get_asgi_application()

# WebSocket routing (향후 실시간 채팅 구현용)
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    # "websocket": AuthMiddlewareStack(
    #     URLRouter([
    #         # WebSocket URL patterns will go here
    #     ])
    # ),
})