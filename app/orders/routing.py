# app/orders/routing.py
from django.urls import re_path
from app.orders.consumers import OrderConsumer

websocket_urlpatterns = [
    # Con business_id específico
    re_path(r'ws/orders/(?P<business_id>\d+)/$', OrderConsumer.as_asgi()),
    # Fallback sin business_id (obtiene del contexto del usuario)
    re_path(r'ws/orders/$', OrderConsumer.as_asgi()),
]