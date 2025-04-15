from rest_framework import viewsets, generics, permissions, status
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Business,CustomUser
from .serializers import BusinessSerializer, UserSerializer
from django.contrib.auth.models import Group
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import BusinessRoleSerializer, RolePermissionSerializer, BusinessRoleUpdateSerializer
from .models import BusinessRole
from django.core.exceptions import PermissionDenied, ValidationError


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
        
        from .services import DatabaseService
        success = DatabaseService.create_business_database(business)
        
        if not success:
            print(f"Advertencia: No se pudo crear la base de datos para el negocio {business.name}")
        

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

        return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

class UserInfoView(generics.RetrieveAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
    
class BusinessRoleViewSet(viewsets.ModelViewSet):
    """
    Endpoints para gestionar roles personalizados de un negocio.
    Solo los administradores pueden crear, modificar y eliminar roles.
    """
    serializer_class = BusinessRoleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Solo mostrar roles del negocio del usuario autenticado
        if not self.request.user.business:
            return BusinessRole.objects.none()
            
        return BusinessRole.objects.filter(business=self.request.user.business)
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['business'] = self.request.user.business
        return context
    
    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return BusinessRoleUpdateSerializer
        return BusinessRoleSerializer
    
    def perform_create(self, serializer):
        # Verificar que el usuario tiene permiso para gestionar roles
        user = self.request.user
        if not user.has_business_permission('can_manage_roles'):
            raise PermissionDenied("No tienes permiso para crear roles")
            
        serializer.save(business=user.business)
    
    def perform_update(self, serializer):
        # Verificar que el usuario tiene permiso y que el rol se puede modificar
        user = self.request.user
        instance = self.get_object()
        
        if not user.has_business_permission('can_manage_roles'):
            raise PermissionDenied("No tienes permiso para modificar roles")
            
        if not instance.can_modify:
            raise PermissionDenied("Este rol no se puede modificar")
            
        serializer.save()
    
    def perform_destroy(self, instance):
        # Verificar que el usuario tiene permiso y que el rol se puede eliminar
        user = self.request.user
        
        if not user.has_business_permission('can_manage_roles'):
            raise PermissionDenied("No tienes permiso para eliminar roles")
            
        if not instance.can_modify:
            raise PermissionDenied("Este rol no se puede eliminar")
            
        # Verificar que no haya usuarios con este rol
        if instance.users.exists():
            raise ValidationError("No se puede eliminar un rol que tiene usuarios asignados")
            
        instance.delete()


class AssignRoleToUserView(APIView):
    """
    Endpoint para asignar un rol específico a un usuario dentro del mismo negocio.
    Solo los administradores pueden asignar roles.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        user_id = request.data.get('user_id')
        role_id = request.data.get('role_id')
        
        if not user_id or not role_id:
            return Response(
                {"error": "Se requieren user_id y role_id"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar permisos del usuario autenticado
        if not request.user.has_business_permission('can_manage_users'):
            return Response(
                {"error": "No tienes permiso para asignar roles"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Obtener el usuario y el rol, verificando que pertenezcan al mismo negocio
            target_user = CustomUser.objects.get(
                id=user_id, 
                business=request.user.business
            )
            
            role = BusinessRole.objects.get(
                id=role_id,
                business=request.user.business
            )
            
            # Asignar el rol
            target_user.business_role = role
            target_user.save(update_fields=['business_role'])
            
            return Response({
                "message": f"Rol {role.name} asignado correctamente a {target_user.username}"
            })
            
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "Usuario no encontrado en tu negocio"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except BusinessRole.DoesNotExist:
            return Response(
                {"error": "Rol no encontrado en tu negocio"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Error al asignar rol: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RolePermissionUpdateView(APIView):
    """
    Endpoint para actualizar los permisos de un rol específico.
    Solo los administradores pueden modificar permisos.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def patch(self, request, role_id):
        # Verificar permisos del usuario autenticado
        if not request.user.has_business_permission('can_manage_roles'):
            return Response(
                {"error": "No tienes permiso para modificar permisos de roles"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Obtener el rol, verificando que pertenezca al negocio del usuario
            role = BusinessRole.objects.get(
                id=role_id,
                business=request.user.business
            )
            
            # Verificar que el rol se puede modificar
            if not role.can_modify:
                return Response(
                    {"error": "Este rol no se puede modificar"}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Actualizar los permisos
            permissions = role.role_permissions
            serializer = RolePermissionSerializer(permissions, data=request.data, partial=True)
            
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            else:
                return Response(
                    serializer.errors, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except BusinessRole.DoesNotExist:
            return Response(
                {"error": "Rol no encontrado en tu negocio"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Error al actualizar permisos: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class UserPermissionsView(APIView):
    """
    Devuelve los permisos del usuario actual basados en su rol de negocio.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Si no tiene rol de negocio, devolver permisos vacíos
        if not user.business_role:
            return Response({
                "role": None,
                "permissions": {}
            })
            
        # Obtener permisos del rol
        try:
            role = user.business_role
            permissions = role.role_permissions
            
            # Convertir el modelo de permisos a diccionario
            permission_dict = {}
            for field in permissions._meta.get_fields():
                if field.name.startswith('can_'):
                    permission_dict[field.name] = getattr(permissions, field.name)
                    
            return Response({
                "role": {
                    "id": role.id,
                    "name": role.name,
                    "is_default": role.is_default,
                    "can_modify": role.can_modify
                },
                "permissions": permission_dict
            })
        except Exception as e:
            return Response(
                {"error": f"Error al obtener permisos: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
