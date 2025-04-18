# API views for managing user authentication, business roles, and permissions.
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

# Models    
from app.accounts.models.user import CustomUser
from app.roles.models.role import BusinessRole

# Serializers
from app.roles.api.serializers import (BusinessRoleSerializer, RolePermissionSerializer,BusinessRoleUpdateSerializer)

# Validators
from django.core.exceptions import PermissionDenied, ValidationError
import logging

logger = logging.getLogger(__name__)


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