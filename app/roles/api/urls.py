# Django imports
from django.urls import path, include

# Django REST Framework imports
from rest_framework.routers import DefaultRouter

# Viewsas imports
from app.roles.api.views.role_views import BusinessRoleViewSet, AssignRoleToUserView, RolePermissionUpdateView, UserPermissionsView



# Configurar el router para BusinessRoleViewSet
router = DefaultRouter()
router.register(r'roles', BusinessRoleViewSet, basename='business-role')

urlpatterns = [
    # Business and role management endpoints
    path("assign-role/", AssignRoleToUserView.as_view(), name="assign_role"),
    path("roles/<int:role_id>/permissions/", RolePermissionUpdateView.as_view(), name="update_role_permissions"),
    path("permissions/", UserPermissionsView.as_view(), name="user_permissions"),
    path('', include(router.urls)),  # Include router URLs for roles
]
