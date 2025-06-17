# app/settings/api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from app.settings.api.views import (
    UserSettingsViewSet,
    BusinessSettingsViewSet,
    NotificationTemplateViewSet,
    SettingsSummaryViewSet
)

router = DefaultRouter()
router.register(r'user', UserSettingsViewSet, basename='user-settings')
router.register(r'business', BusinessSettingsViewSet, basename='business-settings')
router.register(r'notifications', NotificationTemplateViewSet, basename='notification-templates')
router.register(r'summary', SettingsSummaryViewSet, basename='settings-summary')

urlpatterns = [
    path('', include(router.urls)),
]

# URLs disponibles:
# GET/PUT/PATCH /api/settings/user/ - Configuraciones de usuario
# POST /api/settings/user/reset_to_defaults/ - Resetear configuraciones de usuario
# GET/PUT/PATCH /api/settings/business/ - Configuraciones de negocio
# POST /api/settings/business/reset_to_defaults/ - Resetear configuraciones de negocio
# GET/POST/PUT/PATCH/DELETE /api/settings/notifications/ - Plantillas de notificación
# POST /api/settings/notifications/create_default_templates/ - Crear plantillas por defecto
# GET /api/settings/summary/ - Resumen de todas las configuraciones
# POST /api/settings/summary/export_settings/ - Exportar configuraciones