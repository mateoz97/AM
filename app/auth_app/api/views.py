# API views for managing user authentication, business roles, and permissions.
from rest_framework import viewsets, generics, permissions, status
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework import serializers

# Models    
from app.auth_app.models.business import Business, BusinessJoinRequest, BusinessInvitation
from app.auth_app.models.user import CustomUser
from app.auth_app.models.role import BusinessRole

# Serializers
from .serializers import (BusinessSerializer, UserSerializer, 
                          BusinessRoleSerializer, RolePermissionSerializer, 
                          BusinessRoleUpdateSerializer, BusinessJoinRequestSerializer)

# Validators
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


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
        class JoinRequestSerializer(serializers.Serializer):
            business = serializers.IntegerField(required=True)
            message = serializers.CharField(required=False, allow_blank=True)
            
        serializer = JoinRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        
        business_id = request.data.get("business")
        message = request.data.get("message", "")  # Mensaje opcional
        
        # Validación básica
        if not business_id:
            return Response({"error": "Se requiere un ID de negocio"}, status=400)
        
        # Validar que el usuario no pertenezca ya a un negocio
        if request.user.business:
            return Response({
                "error": "Ya perteneces a un negocio. Debes salir primero para solicitar unirte a otro."
            }, status=400)
            
        try:
            business = Business.objects.get(id=business_id)
            
            # Verificar si ya existe una solicitud pendiente o aprobada
            existing_request = BusinessJoinRequest.objects.filter(
                user=request.user,
                business=business
            ).exclude(status='rejected').first()
            
            if existing_request:
                if existing_request.status == 'pending':
                    return Response({
                        "error": "Ya tienes una solicitud pendiente para este negocio",
                        "request_id": existing_request.id
                    }, status=400)
                elif existing_request.status == 'approved':
                    return Response({
                        "error": "Ya tienes una solicitud aprobada para este negocio",
                        "request_id": existing_request.id
                    }, status=400)
            
            # Crear nueva solicitud
            join_request = BusinessJoinRequest.objects.create(
                user=request.user,
                business=business,
                message=message  # Añadir el mensaje si se proporciona
            )
            
            # Serializar para la respuesta
            from .serializers import BusinessJoinRequestSerializer
            serializer = BusinessJoinRequestSerializer(join_request)
            
            # Aquí podríamos enviar una notificación al propietario del negocio
            # TODO: Implementar sistema de notificaciones
            
            return Response({
                "message": "Solicitud enviada exitosamente. El propietario debe aprobarla.",
                "request": serializer.data
            }, status=201)  # 201 Created
            
        except Business.DoesNotExist:
            return Response({"error": "Negocio no encontrado."}, status=404)
        except Exception as e:
            return Response({"error": f"Error: {str(e)}"}, status=500)
    
    def get(self, request):
        """Obtener solicitudes pendientes enviadas por el usuario"""
        requests = BusinessJoinRequest.objects.filter(
            user=request.user
        ).order_by('-created_at')
        
        from .serializers import BusinessJoinRequestSerializer
        serializer = BusinessJoinRequestSerializer(requests, many=True)
        
        return Response(serializer.data)
        
class BusinessJoinRequestManagementView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Ver solicitudes pendientes para el negocio del usuario"""
        if not request.user.business or not request.user.has_business_permission('can_manage_users'):
            return Response({"error": "No tienes permiso para ver solicitudes"}, status=403)
            
        # Filtrar por estado si se proporciona
        status_filter = request.query_params.get('status', 'pending')
        
        if status_filter == 'all':
            pending_requests = BusinessJoinRequest.objects.filter(
                business=request.user.business
            )
        else:
            pending_requests = BusinessJoinRequest.objects.filter(
                business=request.user.business,
                status=status_filter
            )
        
        # Ordenar por fecha de creación (más recientes primero)
        pending_requests = pending_requests.order_by('-created_at')
        
        serializer = BusinessJoinRequestSerializer(pending_requests, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        """Aprobar o rechazar una solicitud"""
        request_id = request.data.get('request_id')
        action = request.data.get('action')  # 'approve' o 'reject'
        role_name = request.data.get('role_name')  # Opcional
        
        if not request_id or not action:
            return Response({"error": "Se requiere request_id y action"}, status=400)
            
        if not request.user.business or not request.user.has_business_permission('can_manage_users'):
            return Response({"error": "No tienes permiso para gestionar solicitudes"}, status=403)
            
        try:
            # Verificar que la solicitud pertenezca al negocio del usuario
            join_request = BusinessJoinRequest.objects.get(
                id=request_id, 
                business=request.user.business,
                status='pending'
            )
            
            # Usar el servicio para procesar la solicitud
            from app.auth_app.services import BusinessJoinService
            success = BusinessJoinService.process_join_request(
                request_id=request_id,
                approve=(action == 'approve'),
                role_name=role_name
            )
            
            if success:
                message = "Solicitud aprobada exitosamente" if action == 'approve' else "Solicitud rechazada"
                return Response({"message": message})
            else:
                return Response({"error": "Error al procesar la solicitud"}, status=500)
                
        except BusinessJoinRequest.DoesNotExist:
            return Response({"error": "Solicitud no encontrada o ya procesada"}, status=404)
        
class BusinessInvitationCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        if not request.user.business or not request.user.has_business_permission('can_manage_users'):
            return Response({"error": "No tienes permiso para crear invitaciones"}, status=403)
            
        role_id = request.data.get('role_id')  # Opcional
        expiration_days = request.data.get('expiration_days', 7)  # Por defecto 7 días
        
        try:
            # Verificar rol si se proporciona
            role = None
            if role_id:
                role = BusinessRole.objects.get(
                    id=role_id,
                    business=request.user.business
                )
                
            # Usar el servicio para crear la invitación
            from app.auth_app.services import BusinessJoinService
            invitation = BusinessJoinService.create_invitation(
                business=request.user.business,
                created_by=request.user,
                role=role,
                expires_days=expiration_days
            )
            
            if not invitation:
                return Response({"error": "Error al crear invitación"}, status=500)
            
            # Serializar la respuesta
            from .serializers import BusinessInvitationSerializer
            serializer = BusinessInvitationSerializer(invitation)
            
            return Response({
                "message": "Invitación creada exitosamente",
                "invitation": serializer.data
            }, status=201)
            
        except BusinessRole.DoesNotExist:
            return Response({"error": "Rol no encontrado"}, status=404)
        except Exception as e:
            return Response({"error": f"Error al crear invitación: {str(e)}"}, status=500)

        
class BusinessInvitationUseView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        token = request.data.get('token')
        
        if not token:
            return Response({"error": "Se requiere token de invitación"}, status=400)
            
        # Verificar si el usuario ya pertenece a un negocio
        if request.user.business:
            return Response(
                {"error": "Ya perteneces a un negocio. Debes salir primero para unirte a otro."},
                status=400
            )
        
        # Usar el servicio para procesar la invitación
        from app.auth_app.services import BusinessJoinService
        result = BusinessJoinService.use_invitation(request.user, token)
        
        if result['success']:
            return Response({
                "message": result['message'],
                "business": result['data']['business'].name,
                "role": result['data']['role'].name
            })
        else:
            return Response({"error": result['message']}, status=400)

class UserBusinessInvitationsListView(APIView):
    """
    Endpoint para listar invitaciones creadas por el usuario
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        if not request.user.business or not request.user.has_business_permission('can_manage_users'):
            return Response({"error": "No tienes permiso para ver invitaciones"}, status=403)
        
        # Obtener invitaciones activas del negocio del usuario
        invitations = BusinessInvitation.objects.filter(
            business=request.user.business,
            used=False,
            expires_at__gt=timezone.now()
        )
        
        from .serializers import BusinessInvitationSerializer
        serializer = BusinessInvitationSerializer(invitations, many=True)
        
        return Response(serializer.data)
    
    
class LeaveBusinessView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Permite a un usuario salir del negocio al que pertenece"""
        if not request.user.business:
            return Response({"error": "No perteneces a ningún negocio"}, status=400)
        
        # Verificar si el usuario es el propietario del negocio
        if request.user.business.owner == request.user:
            return Response({
                "error": "Eres el propietario del negocio. No puedes salir, debes transferir la propiedad primero."
            }, status=400)
        
        # Guardar para la respuesta
        business_name = request.user.business.name
        
        # Remover al usuario del negocio
        request.user.business = None
        request.user.business_role = None
        request.user.save(update_fields=['business', 'business_role'])
        
        return Response({
            "message": f"Has salido exitosamente del negocio {business_name}"
        })
        