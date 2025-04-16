# Django imports
from django.urls import path

# Django REST Framework imports
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

# Viewsas imports
from app.accounts.api.views.auth_views import RegisterUserView, CustomLoginView, UserInfoView




urlpatterns = [
    # Authentication endpoints
    path('login/', CustomLoginView.as_view(), name='login'),
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("register/", RegisterUserView.as_view(), name="register"),
    
    # User management endpoints
    path("user-info/", UserInfoView.as_view(), name="user_info"),

]