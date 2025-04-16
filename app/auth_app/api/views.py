# API views for managing user authentication, business roles, and permissions.
from rest_framework import viewsets, generics, permissions, status
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

# Models    
from app.auth_app.models import Business,CustomUser,BusinessRole, BusinessJoinRequest, BusinessInvitation

# Serializers
from .serializers import (BusinessSerializer, UserSerializer, 
                          BusinessRoleSerializer, RolePermissionSerializer, 
                          BusinessRoleUpdateSerializer, BusinessJoinRequestSerializer)

# Validators
from django.core.exceptions import PermissionDenied, ValidationError


class BusinessViewSet(viewsets.ModelViewSet):
    queryset = Business.objects.all()
    serializer_class = BusinessSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        business = serializer.save(owner=self.request.user)
        self.request.user.business = business
        
        # Crear roles para el negocio
        from ..services import BusinessRoleService
        roles = BusinessRoleService.create_default_roles(business)
        
        # Asignar rol de administrador al creador
        admin_role = roles.get("Admin") or roles.get("Administrador")
        if admin_role:
            self.request.user.business_role = admin_role
            self.request.user.save(update_fields=['business', 'business_role'])
        
        # Crear base de datos para el negocio - Asegurarse que esto se ejecute
        print(f"Creando base de datos para negocio: {business.name} ({business.id})")
        from ..services import DatabaseService
        success = DatabaseService.create_business_database(business)
        
        if not success:
            print(f"Advertencia: No se pudo crear la base de datos para el negocio {business.name}")
        
class JoinBusinessView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request):
        business_id = request.data.get("business")
        try:
            business = Business.objects.get(id=business_id)
            
            # Obtener rol predeterminado (Mesero o Visualizador)
            from ..services import BusinessRoleService
            roles = BusinessRoleService.get_roles_for_business(business)
            default_role = roles.filter(name="viewer").first() or roles.filter(is_default=True).first()
            
            if not default_role:
                # Si no hay roles, crearlos
                roles_dict = BusinessRoleService.create_default_roles(business)
                default_role = roles_dict.get("viewer")

            request.user.business = business
            request.user.business_role = default_role
            request.user.save()

            return Response({
                "message": "Usuario unido al negocio exitosamente.", 
                "role": default_role.name
            }, status=200)
        except Business.DoesNotExist:
            return Response({"error": "Negocio no encontrado."}, status=404)
        except Exception as e:
            return Response({"error": f"Error: {str(e)}"}, status=400)
          
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

class JoinBusinessRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        business_id = request.data.get("business")
        try:
            business = Business.objects.get(id=business_id)
            
            # Verificar si ya existe una solicitud pendiente
            existing_request = BusinessJoinRequest.objects.filter(
                user=request.user,
                business=business,
                status='pending'
            ).exists()
            
            if existing_request:
                return Response({"error": "Ya tienes una solicitud pendiente para este negocio"}, status=400)
            
            # Crear nueva solicitud
            join_request = BusinessJoinRequest.objects.create(
                user=request.user,
                business=business
            )
            
            return Response({
                "message": "Solicitud enviada exitosamente. El propietario debe aprobarla.",
                "request_id": join_request.id
            }, status=201)
            
        except Business.DoesNotExist:
            return Response({"error": "Negocio no encontrado."}, status=404)
        
class BusinessJoinRequestManagementView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Ver solicitudes pendientes para el negocio del usuario"""
        if not request.user.business or not request.user.has_business_permission('can_manage_users'):
            return Response({"error": "No tienes permiso para ver solicitudes"}, status=403)
            
        pending_requests = BusinessJoinRequest.objects.filter(
            business=request.user.business,
            status='pending'
        )
        
        serializer = BusinessJoinRequestSerializer(pending_requests, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        """Aprobar o rechazar una solicitud"""
        request_id = request.data.get('request_id')
        action = request.data.get('action')  # 'approve' o 'reject'
        
        if not request_id or not action:
            return Response({"error": "Se requiere request_id y action"}, status=400)
            
        if not request.user.business or not request.user.has_business_permission('can_manage_users'):
            return Response({"error": "No tienes permiso para gestionar solicitudes"}, status=403)
            
        try:
            join_request = BusinessJoinRequest.objects.get(
                id=request_id, 
                business=request.user.business,
                status='pending'
            )
            
            if action == 'approve':
                # Asignar rol de visualizador
                join_request.status = 'approved'
                
                # Buscar rol de visualizador
                viewer_role = BusinessRole.objects.filter(
                    business=request.user.business,
                    name__in=['Visualizador', 'viewer']
                ).first()
                
                # Asignar negocio y rol al usuario
                user = join_request.user
                user.business = request.user.business
                user.business_role = viewer_role
                user.save(update_fields=['business', 'business_role'])
                
                message = "Solicitud aprobada exitosamente"
            elif action == 'reject':
                join_request.status = 'rejected'
                message = "Solicitud rechazada"
            else:
                return Response({"error": "Acción no válida"}, status=400)
                
            join_request.save()
            return Response({"message": message})
            
        except BusinessJoinRequest.DoesNotExist:
            return Response({"error": "Solicitud no encontrada"}, status=404)
        
