# app/inventory/api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from app.inventory.api.views import (
    ProductViewSet,
    ProductCategoryViewSet,
    StockMovementViewSet
)

# Configurar el router
router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
router.register(r'categories', ProductCategoryViewSet, basename='product-category')
router.register(r'stock-movements', StockMovementViewSet, basename='stock-movement')

urlpatterns = [
    path('', include(router.urls)),
]