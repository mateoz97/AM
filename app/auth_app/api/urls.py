# Django imports
from django.urls import path, include

# Django REST Framework imports
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

# Viewsas imports
from app.auth_app.api.views.auth_views import RegisterUserView, CustomLoginView
from app.auth_app.api.views.user_views import UserInfoView, LeaveBusinessView
from app.auth_app.api.views.role_views import BusinessRoleViewSet, AssignRoleToUserView, RolePermissionUpdateView, UserPermissionsView
from app.auth_app.api.views.request_views import (JoinBusinessView, JoinBusinessRequestView, 
                                                  BusinessJoinRequestManagementView, BusinessInvitationCreateView, 
                                                  BusinessInvitationUseView, UserBusinessInvitationsListView)

# Configurar el router para BusinessRoleViewSet
router = DefaultRouter()
router.register(r'roles', BusinessRoleViewSet, basename='business-role')

urlpatterns = [
    # Authentication endpoints
    path('login/', CustomLoginView.as_view(), name='login'),
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("register/", RegisterUserView.as_view(), name="register"),
    
    # User management endpoints
    path("user-info/", UserInfoView.as_view(), name="user_info"),
    path("leave-business/", LeaveBusinessView.as_view(), name="leave_business"),
    
    # Business and role management endpoints
    path("join-business/", JoinBusinessView.as_view(), name="join_business"),
    path("assign-role/", AssignRoleToUserView.as_view(), name="assign_role"),
    path("roles/<int:role_id>/permissions/", RolePermissionUpdateView.as_view(), name="update_role_permissions"),
    path("permissions/", UserPermissionsView.as_view(), name="user_permissions"),
    path('', include(router.urls)),  # Include router URLs for roles
    
    # Join requests and invitations endpoints
    path("join-business-request/", JoinBusinessRequestView.as_view(), name="join_business_request"),
    path("business-requests/", BusinessJoinRequestManagementView.as_view(), name="business_requests"),
    path("invitations/create/", BusinessInvitationCreateView.as_view(), name="create_invitation"),
    path("invitations/use/", BusinessInvitationUseView.as_view(), name="use_invitation"),
    path("invitations/list/", UserBusinessInvitationsListView.as_view(), name="list_invitations"),
]