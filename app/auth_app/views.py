from rest_framework import viewsets, generics, permissions
from rest_framework.response import Response
from .models import Business
from .serializers import BusinessSerializer, UserSerializer
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.views import APIView


class BusinessViewSet(viewsets.ModelViewSet):
    queryset = Business.objects.all()
    serializer_class = BusinessSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        business = serializer.save(owner=self.request.user)
        admin_role = Group.objects.get(name=f"{business.name}_Admin")
        self.request.user.business = business
        self.request.user.role = admin_role
        self.request.user.groups.add(admin_role)
        self.request.user.save()

class JoinBusinessView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request):
        business_id = request.data.get("business")
        try:
            business = Business.objects.get(id=business_id)
            mesero_role = Group.objects.get(name=f"{business.name}_Mesero")

            request.user.business = business
            request.user.role = mesero_role
            request.user.groups.add(mesero_role)
            request.user.save()

            return Response({"message": "Usuario unido al negocio exitosamente."}, status=200)
        except Business.DoesNotExist:
            return Response({"error": "Negocio no encontrado."}, status=404)
        except Group.DoesNotExist:
            return Response({"error": "El rol Mesero no está definido."}, status=400)



User = get_user_model()

class RegisterUserView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]

class UserInfoView(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    pagination_class = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

