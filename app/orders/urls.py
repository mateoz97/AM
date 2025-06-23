# app/orders/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from app.orders.views import OrderViewSet

# Configurar el router
router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='order')

urlpatterns = [
    path('', include(router.urls)),
]