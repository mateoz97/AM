# app/roles/api/views/role_management_views.py
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
import logging

from app.roles.models.role import BusinessRole
from app.roles.services.role_service import BusinessRoleService
from app.roles.api.serializers import BusinessRoleSerializer

logger = logging.getLogger(__name__)


class BusinessRoleManagementView(APIView):
    """Vista para gestionar roles de negocio (solo para owners)"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Obtiene todos los roles del negocio actual"""
        if not request.user.current_business:
            return Response({
                'error': 'Debes tener un negocio activo'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verificar que sea el propietario del negocio
        if request.user.current_business.owner != request.user:
            return Response({
                'error': 'Solo el propietario puede gestionar roles'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Obtener roles del negocio
        roles = BusinessRole.objects.filter(
            business=request.user.current_business
        ).order_by('name')
        
        serializer = BusinessRoleSerializer(roles, many=True)
        return Response({
            'roles': serializer.data,
            'role_templates': BusinessRoleService.create_default_role_templates()
        })
    
    def post(self, request):
        """Crea un nuevo rol personalizado"""
        if not request.user.current_business:
            return Response({
                'error': 'Debes tener un negocio activo'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verificar que sea el propietario del negocio
        if request.user.current_business.owner != request.user:
            return Response({
                'error': 'Solo el propietario puede crear roles'
            }, status=status.HTTP_403_FORBIDDEN)
        
        name = request.data.get('name')
        description = request.data.get('description', '')
        permissions_data = request.data.get('permissions', {})
        
        if not name:
            return Response({
                'error': 'El nombre del rol es requerido'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verificar que el nombre no esté en uso
        if BusinessRole.objects.filter(
            business=request.user.current_business,
            name=name
        ).exists():
            return Response({
                'error': 'Ya existe un rol con ese nombre'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                # Crear el rol personalizado
                role = BusinessRoleService.create_custom_role(
                    business=request.user.current_business,
                    name=name,
                    description=description,
                    permissions_data=permissions_data
                )
                
                if role:
                    serializer = BusinessRoleSerializer(role)
                    return Response({
                        'message': f'Rol "{name}" creado exitosamente',
                        'role': serializer.data
                    }, status=status.HTTP_201_CREATED)
                else:
                    return Response({
                        'error': 'Error al crear el rol'
                    }, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            logger.error(f"Error al crear rol: {str(e)}")
            return Response({
                'error': 'Error interno al crear el rol'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def put(self, request, role_id):
        """Actualiza un rol existente"""
        if not request.user.current_business:
            return Response({
                'error': 'Debes tener un negocio activo'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verificar que sea el propietario del negocio
        if request.user.current_business.owner != request.user:
            return Response({
                'error': 'Solo el propietario puede modificar roles'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            role = BusinessRole.objects.get(
                id=role_id,
                business=request.user.current_business
            )
        except BusinessRole.DoesNotExist:
            return Response({
                'error': 'Rol no encontrado'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Verificar que el rol sea modificable
        if not role.can_modify:
            return Response({
                'error': 'Este rol no puede ser modificado'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        description = request.data.get('description', role.description)
        permissions_data = request.data.get('permissions', {})
        
        try:
            with transaction.atomic():
                # Actualizar descripción
                role.description = description
                role.save()
                
                # Actualizar permisos
                if permissions_data:
                    permissions = role.role_permissions
                    for perm_name, perm_value in permissions_data.items():
                        if hasattr(permissions, perm_name):
                            setattr(permissions, perm_name, perm_value)
                    permissions.save()
                
                serializer = BusinessRoleSerializer(role)
                return Response({
                    'message': f'Rol "{role.name}" actualizado exitosamente',
                    'role': serializer.data
                })
        
        except Exception as e:
            logger.error(f"Error al actualizar rol: {str(e)}")
            return Response({
                'error': 'Error interno al actualizar el rol'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request, role_id):
        """Elimina un rol (solo si no está siendo usado)"""
        if not request.user.current_business:
            return Response({
                'error': 'Debes tener un negocio activo'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verificar que sea el propietario del negocio
        if request.user.current_business.owner != request.user:
            return Response({
                'error': 'Solo el propietario puede eliminar roles'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            role = BusinessRole.objects.get(
                id=role_id,
                business=request.user.current_business
            )
        except BusinessRole.DoesNotExist:
            return Response({
                'error': 'Rol no encontrado'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Verificar que el rol sea modificable
        if not role.can_modify:
            return Response({
                'error': 'Este rol no puede ser eliminado'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verificar que no esté siendo usado por ningún usuario
        from app.accounts.models.user import CustomUser
        users_with_role = CustomUser.objects.filter(current_business_role=role)
        if users_with_role.exists():
            return Response({
                'error': f'No se puede eliminar el rol porque está siendo usado por {users_with_role.count()} usuario(s)'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            role_name = role.name
            role.delete()
            return Response({
                'message': f'Rol "{role_name}" eliminado exitosamente'
            })
        
        except Exception as e:
            logger.error(f"Error al eliminar rol: {str(e)}")
            return Response({
                'error': 'Error interno al eliminar el rol'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RoleTemplatesView(APIView):
    """Vista para obtener plantillas de roles disponibles"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Obtiene las plantillas de roles disponibles"""
        if not request.user.current_business:
            return Response({
                'error': 'Debes tener un negocio activo'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verificar que sea el propietario del negocio
        if request.user.current_business.owner != request.user:
            return Response({
                'error': 'Solo el propietario puede ver plantillas de roles'
            }, status=status.HTTP_403_FORBIDDEN)
        
        templates = BusinessRoleService.create_default_role_templates()
        return Response({
            'templates': templates
        })


class CreateRoleFromTemplateView(APIView):
    """Vista para crear un rol desde una plantilla"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Crea un rol desde una plantilla predefinida"""
        if not request.user.current_business:
            return Response({
                'error': 'Debes tener un negocio activo'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verificar que sea el propietario del negocio
        if request.user.current_business.owner != request.user:
            return Response({
                'error': 'Solo el propietario puede crear roles'
            }, status=status.HTTP_403_FORBIDDEN)
        
        template_name = request.data.get('template_name')
        custom_name = request.data.get('custom_name')  # Opcional: nombre personalizado
        
        if not template_name:
            return Response({
                'error': 'El nombre de la plantilla es requerido'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Obtener la plantilla
        templates = BusinessRoleService.create_default_role_templates()
        template = templates.get(template_name)
        
        if not template:
            return Response({
                'error': 'Plantilla no encontrada'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Usar nombre personalizado o el de la plantilla
        role_name = custom_name if custom_name else template_name
        
        # Verificar que el nombre no esté en uso
        if BusinessRole.objects.filter(
            business=request.user.current_business,
            name=role_name
        ).exists():
            return Response({
                'error': 'Ya existe un rol con ese nombre'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                # Crear el rol desde la plantilla
                role = BusinessRoleService.create_custom_role(
                    business=request.user.current_business,
                    name=role_name,
                    description=template['description'],
                    permissions_data=template['permissions']
                )
                
                if role:
                    serializer = BusinessRoleSerializer(role)
                    return Response({
                        'message': f'Rol "{role_name}" creado exitosamente desde plantilla',
                        'role': serializer.data
                    }, status=status.HTTP_201_CREATED)
                else:
                    return Response({
                        'error': 'Error al crear el rol desde la plantilla'
                    }, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            logger.error(f"Error al crear rol desde plantilla: {str(e)}")
            return Response({
                'error': 'Error interno al crear el rol'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)