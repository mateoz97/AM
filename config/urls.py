from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from app.debug_views import debug_user_status, debug_public_status

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/accounts/', include('app.accounts.api.urls')),
    path('api/business/', include('app.business.api.urls')),
    path('api/roles/', include('app.roles.api.urls')),
    path('api/posts/', include('app.posts.api.urls')),
    path('api/inventory/', include('app.inventory.api.urls')),  
    path('api/settings/', include('app.settings.api.urls')),
    path('api/', include('app.orders.urls')),  # Orders API
    
    # Debug endpoints
    path('api/debug/user-status/', debug_user_status, name='debug_user_status'),
    path('api/debug/public/', debug_public_status, name='debug_public_status'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
