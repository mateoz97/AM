from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/accounts/', include('app.accounts.api.urls')),
    path('api/business/', include('app.business.api.urls')),
    path('api/roles/', include('app.roles.api.urls')),
    path('api/posts/', include('app.posts.api.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
