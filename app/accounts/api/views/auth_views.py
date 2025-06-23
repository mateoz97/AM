# API views for managing user authentication, business roles, and permissions.
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

# Models    
from app.accounts.models.user import CustomUser

# Serializers
from app.accounts.api.serializers import UserSerializer, LoginSerializer, UserProfileSerializer

# Validators
import logging

logger = logging.getLogger(__name__)

class RegisterUserView(generics.CreateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            
            # Log registro exitoso
            logger.info(f"Nuevo usuario registrado: {user.username} (ID: {user.id})")
            
            # Generar tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                "user": serializer.data,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }, status=status.HTTP_201_CREATED)
            
        except serializers.ValidationError as e:
            logger.warning(f"Error de validación en registro: {e.detail}")
            raise e
        except Exception as e:
            logger.error(f"Error inesperado durante registro: {str(e)}", exc_info=True)
            return Response({
                "error": "Error interno durante el registro"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CustomLoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        
        # Generar tokens
        refresh = RefreshToken.for_user(user)
        
        # Serializar el usuario completo con información de negocio y rol
        user_serializer = UserSerializer(user)
        
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": user_serializer.data
        })

class UserInfoView(generics.RetrieveAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
    
class UserProfileView(generics.UpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user