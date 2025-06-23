# app/orders/routing.py
from django.urls import re_path
from app.orders.consumers import OrderConsumer

websocket_urlpatterns = [
    re_path(r'ws/orders/(?P<business_id>\d+)/$', OrderConsumer.as_asgi()),
]