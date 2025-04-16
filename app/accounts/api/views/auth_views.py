# API views for managing user authentication, business roles, and permissions.
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

# Models    
from app.accounts.models.user import CustomUser


# Serializers
from app.accounts.api.serializers import UserSerializer

# Validators
import logging

logger = logging.getLogger(__name__)

class RegisterUserView(generics.CreateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        print(user)
        
        refresh = RefreshToken.for_user(user)
        
        access_token = str(refresh.access_token)

        return Response({
            "user": serializer.data,
            "refresh": str(refresh),
            "access": access_token,
        }, status=status.HTTP_201_CREATED)

class CustomLoginView(TokenObtainPairView):
    
    def post(self, request, *args, **kwargs):
        identifier = request.data.get("username")  # Puede ser username o email
        password = request.data.get("password")

        user = CustomUser.objects.filter(email=identifier).first() or CustomUser.objects.filter(username=identifier).first()

        if user and user.check_password(password):
            refresh = RefreshToken.for_user(user)
            return Response({
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "username": user.username
            })
