from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('app.auth_app.urls')),
    path('api/ping/', include('app.ping.urls')), 
]