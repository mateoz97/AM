# app/posts/api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from app.posts.api.views import PostViewSet

router = DefaultRouter()
router.register(r'', PostViewSet, basename='post')

urlpatterns = [
    path('', include(router.urls)),
]