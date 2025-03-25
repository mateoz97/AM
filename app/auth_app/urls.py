from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import RegisterUserView, JoinBusinessView, UserInfoView

urlpatterns = [
    path("login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("register/", RegisterUserView.as_view(), name="register"),
    path("join-business/", JoinBusinessView.as_view(), name="join_business"),
    path("user-info/", UserInfoView.as_view(), name="user_info"),
]