# Django imports
from django.urls import path, include

# Django REST Framework imports
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

# Viewsas imports
from .views import (
    RegisterUserView, JoinBusinessView, UserInfoView, CustomLoginView,
    BusinessRoleViewSet, AssignRoleToUserView, RolePermissionUpdateView,
    UserPermissionsView, JoinBusinessRequestView,
    BusinessJoinRequestManagementView, BusinessInvitationCreateView,
    BusinessInvitationUseView, UserBusinessInvitationsListView,
    LeaveBusinessView
)

# Configurar el router para BusinessRoleViewSet
router = DefaultRouter()
router.register(r'roles', BusinessRoleViewSet, basename='business-role')

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("register/", RegisterUserView.as_view(), name="register"),
    path("join-business/", JoinBusinessView.as_view(), name="join_business"),
    path("user-info/", UserInfoView.as_view(), name="user_info"),
    path("assign-role/", AssignRoleToUserView.as_view(), name="assign_role"),
    path("roles/<int:role_id>/permissions/", RolePermissionUpdateView.as_view(), name="update_role_permissions"),
    path('', include(router.urls)),
    path("permissions/", UserPermissionsView.as_view(), name="user_permissions"),
    path("join-business-request/", JoinBusinessRequestView.as_view(), name="join_business_request"),
    path("business-requests/", BusinessJoinRequestManagementView.as_view(), name="business_requests"),
    path("invitations/create/", BusinessInvitationCreateView.as_view(), name="create_invitation"),
    path("invitations/use/", BusinessInvitationUseView.as_view(), name="use_invitation"),
    path("invitations/list/", UserBusinessInvitationsListView.as_view(), name="list_invitations"),
    path("leave-business/", LeaveBusinessView.as_view(), name="leave_business"),
]