from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/accounts/', include('app.accounts.api.urls')),
    path('api/business/', include('app.business.api.urls')),
    path('api/roles/', include('app.roles.api.urls')),
]