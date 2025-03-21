from django.urls import path
from .views import ping_view

urlpatterns = [
    path('', ping_view, name='ping'),
]