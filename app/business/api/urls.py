# app/business/api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from app.business.api.views.request_views import (
    JoinBusinessRequestView,
    BusinessJoinRequestManagementView,
    BusinessInvitationCreateView,
    BusinessInvitationUseView,
    UserBusinessInvitationsListView,
)
from app.business.api.views.business_views import (
    LeaveBusinessView, 
    JoinBusinessView,
    BusinessViewSet,
    SwitchBusinessView  # ✅ Asegurar que esté importado
)

# Configurar el router para BusinessViewSet
router = DefaultRouter()
router.register(r'', BusinessViewSet, basename='business')

urlpatterns = [
    # ✅ IMPORTANTE: Las rutas específicas DEBEN ir ANTES del router
    path("switch-business/", SwitchBusinessView.as_view(), name="switch_business"),
    path("join-business/", JoinBusinessView.as_view(), name="join_business"),
    path("leave-business/", LeaveBusinessView.as_view(), name="leave_business"),
    
    # Join requests and invitations endpoints
    path("join-business-request/", JoinBusinessRequestView.as_view(), name="join_business_request"),
    path("business-requests/", BusinessJoinRequestManagementView.as_view(), name="business_requests"),
    path("invitations/create/", BusinessInvitationCreateView.as_view(), name="create_invitation"),
    path("invitations/use/", BusinessInvitationUseView.as_view(), name="use_invitation"),
    path("invitations/list/", UserBusinessInvitationsListView.as_view(), name="list_invitations"),
    
    # ✅ Business ViewSet endpoints (incluye user-businesses) - AL FINAL
    path('', include(router.urls)),
]