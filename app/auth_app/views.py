from rest_framework import viewsets, generics, permissions
from .models import Business
from .serializers import BusinessSerializer, UserSerializer
from django.contrib.auth import get_user_model


class BusinessViewSet(viewsets.ModelViewSet):
    queryset = Business.objects.all()
    serializer_class = BusinessSerializer


User = get_user_model()

class RegisterUserView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]

