# API views for managing user authentication, business roles, and permissions.
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action

# Models    
from django.db import models
from app.business.models.business import Business

# Serializers
from app.business.api.serializers import BusinessSerializer

# Validators
import logging

logger = logging.getLogger(__name__)

class BusinessViewSet(viewsets.ModelViewSet):
    serializer_class = BusinessSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filtra negocios según el contexto"""
        user = self.request.user
        
        # Si es superusuario, puede ver todos
        if user.is_superuser:
            return Business.objects.all()
        
        # Para usuarios normales, ver negocios donde tienen algún rol
        user_businesses = Business.objects.filter(
            models.Q(owner=user) | 
            models.Q(co_owners=user) | 
            models.Q(business_roles__users=user)
        ).distinct()
        
        return user_businesses

    def perform_create(self, serializer):
        # Guardar el negocio con el usuario actual como propietario
        business = serializer.save(owner=self.request.user)
        
        # Actualizar el usuario para asignarle el negocio creado
        self.request.user.business = business
        
        # Crear roles para el negocio
        from app.roles.services.role_service import BusinessRoleService
        roles = BusinessRoleService.create_business_roles(business)
        
        # Asignar rol de owner al creador
        owner_role = roles.get("Owner")
        if owner_role:
            self.request.user.current_business_role = owner_role
            self.request.user.current_business = business
            self.request.user.promote_to_business_owner()
            self.request.user.save(update_fields=['current_business', 'current_business_role'])
        
        # Crear base de datos para el negocio - Asegurarse que esto se ejecute
        from app.business.services.business_service import DatabaseService
        logger.info(f"Creando base de datos para negocio: {business.name} (ID: {business.id})")
        success = DatabaseService.create_business_database(business)
        
        if not success:
            logger.warning(f"⚠️ No se pudo crear la base de datos para el negocio {business.name}")
    
    @action(detail=False, methods=['get'], url_path='user-businesses')
    def user_businesses(self, request):
        """
        Obtiene todos los negocios donde el usuario es owner o empleado
        """
        user = request.user
        businesses_data = []
        
        # Negocios propios
        owned_businesses = Business.objects.filter(owner=user)
        for business in owned_businesses:
            businesses_data.append({
                'id': business.id,
                'name': business.name,
                'description': business.description or 'Sede Principal',
                'isOwner': True,
                'role': 'Owner'
            })
        
        # Negocios donde es empleado
        if user.business and user.business not in owned_businesses:
            businesses_data.append({
                'id': user.business.id,
                'name': user.business.name,
                'description': user.business.description or 'Empleado',
                'isOwner': False,
                'role': user.business_role.name if user.business_role else 'Empleado'
            })
        
        # Negocios donde es co-propietario
        co_owned_businesses = user.co_owned_businesses.exclude(
            id__in=[b.id for b in owned_businesses] + 
            ([user.business.id] if user.business else [])
        )
        
        for business in co_owned_businesses:
            businesses_data.append({
                'id': business.id,
                'name': business.name,
                'description': business.description or 'Co-propietario',
                'isOwner': False,
                'role': 'Co-Owner'
            })
        
        return Response(businesses_data)
    
    @action(detail=True, methods=['delete'], url_path='delete-with-schema')
    def delete_with_schema(self, request, pk=None):
        """
        Elimina un negocio junto con su esquema de base de datos
        Solo permite al propietario eliminar el negocio
        """
        try:
            business = self.get_object()
            
            # Verificar permisos - solo el propietario puede eliminar
            if business.owner != request.user and not request.user.is_superuser:
                return Response({
                    'error': 'Solo el propietario del negocio puede eliminarlo'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Verificar si hay otros usuarios dependientes
            active_members = business.get_active_members()
            other_members = [member for member in active_members if member != request.user]
            
            if other_members and not request.data.get('force_delete', False):
                return Response({
                    'error': f'El negocio tiene {len(other_members)} miembros activos. '
                           f'Para eliminar, agrega "force_delete": true al cuerpo de la petición.',
                    'members_count': len(other_members),
                    'members': [{'id': m.id, 'name': m.get_full_name()} for m in other_members[:5]]
                }, status=status.HTTP_400_BAD_REQUEST)
            
            business_name = business.name
            business_id = business.id
            
            # Log de auditoría
            logger.warning(f"Usuario {request.user.id} eliminando negocio {business_name} (ID: {business_id})")
            
            # Desasociar usuarios antes de eliminar
            for member in other_members:
                if member.current_business_id == business_id:
                    member.current_business = None
                    member.current_business_role = None
                    member.save(update_fields=['current_business', 'current_business_role'])
            
            # Eliminar el negocio (esto también elimina el esquema automáticamente)
            business.delete()
            
            # Si el usuario actual tenía este negocio como activo, limpiarlo
            if request.user.current_business_id == business_id:
                request.user.current_business = None
                request.user.current_business_role = None
                request.user.save(update_fields=['current_business', 'current_business_role'])
            
            return Response({
                'message': f'Negocio "{business_name}" eliminado exitosamente junto con su esquema de base de datos',
                'deleted_business_id': business_id,
                'affected_users': len(other_members)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error eliminando negocio {pk}: {str(e)}", exc_info=True)
            return Response({
                'error': f'Error al eliminar el negocio: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'], url_path='schema-status')
    def schema_status(self, request, pk=None):
        """
        Verifica el estado del esquema de base de datos del negocio
        """
        try:
            business = self.get_object()
            
            # Verificar permisos
            if not business.has_access(request.user) and not request.user.is_superuser:
                return Response({
                    'error': 'No tienes acceso a este negocio'
                }, status=status.HTTP_403_FORBIDDEN)
            
            from app.business.services.business_service import DatabaseService
            
            exists, info = DatabaseService.verify_business_database(business.id)
            
            return Response({
                'business_id': business.id,
                'business_name': business.name,
                'schema_exists': exists,
                'schema_info': info,
                'schema_name': DatabaseService.get_business_schema_name(business.id)
            })
            
        except Exception as e:
            logger.error(f"Error verificando esquema del negocio {pk}: {str(e)}")
            return Response({
                'error': f'Error al verificar el esquema: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'], url_path='create-schema')
    def create_schema(self, request, pk=None):
        """
        Crea el esquema de base de datos para el negocio si no existe
        """
        try:
            business = self.get_object()
            
            # Verificar permisos - solo propietarios o admins
            if business.owner != request.user and not request.user.is_superuser:
                return Response({
                    'error': 'Solo el propietario del negocio puede crear su esquema'
                }, status=status.HTTP_403_FORBIDDEN)
            
            from app.business.services.business_service import DatabaseService
            
            # Verificar si ya existe
            exists, info = DatabaseService.verify_business_database(business.id)
            if exists:
                return Response({
                    'message': 'El esquema ya existe',
                    'schema_info': info
                }, status=status.HTTP_200_OK)
            
            # Crear el esquema
            success = DatabaseService.create_business_database(business)
            
            if success:
                return Response({
                    'message': f'Esquema creado exitosamente para el negocio "{business.name}"',
                    'schema_name': DatabaseService.get_business_schema_name(business.id)
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'error': 'No se pudo crear el esquema de base de datos'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            logger.error(f"Error creando esquema para negocio {pk}: {str(e)}")
            return Response({
                'error': f'Error al crear el esquema: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
class JoinBusinessView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request):
        business_id = request.data.get("business")
        try:
            business = Business.objects.get(id=business_id)
            
            # Obtener rol predeterminado (Viewer)
            from app.roles.models.role import BusinessRole
            default_role = BusinessRole.objects.filter(
                business=business,
                name__in=["Viewer", "Visualizador"],
                is_default=True
            ).first()
            
            if not default_role:
                # Si no hay roles, crearlos
                from app.roles.services.role_service import BusinessRoleService
                roles_dict = BusinessRoleService.create_business_roles(business)
                default_role = roles_dict.get("Viewer") or roles_dict.get("Visualizador")

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
    
class SwitchBusinessView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Permite a un usuario cambiar su negocio activo"""
        try:
            business_id = request.data.get('business_id')
            
            # Log para auditoría
            logger.info(f"Usuario {request.user.id} intentando cambiar a negocio {business_id}")
            
            if not business_id:
                return Response({"error": "Se requiere business_id"}, status=status.HTTP_400_BAD_REQUEST)
            
            # Verificar que el usuario sea propietario o co-propietario del negocio
            business = Business.objects.get(id=business_id)
            
            is_owner = business.owner == request.user
            is_co_owner = request.user in business.co_owners.all()
            is_member = request.user.current_business == business
            
            if not (is_owner or is_co_owner or is_member):
                return Response({"error": "No tienes acceso a este negocio"}, status=status.HTTP_403_FORBIDDEN)
            
            # Buscar el rol apropiado
            from app.roles.models.role import BusinessRole
            
            if is_owner:
                # Si es propietario, asignar el rol Admin
                role = BusinessRole.objects.filter(business=business, name__in=["Admin", "Administrador"]).first()
            elif is_co_owner:
                # Si es co-propietario, asignar el rol Gerente o similar
                role = BusinessRole.objects.filter(business=business, name__in=["Gerente", "Manager"]).first()
            else:
                # Si es miembro regular, mantener su rol actual o asignar uno básico
                role = request.user.business_role
                
                # Si no tiene un rol en este negocio, asignarle uno apropiado
                if not role or role.business.id != business.id:
                    role = BusinessRole.objects.filter(
                        business=business,
                        name__in=["Viewer", "Visualizador"],
                        is_default=True
                    ).first()
            
            # Si no se encuentra un rol, crear roles por defecto
            if not role:
                from app.roles.services.role_service import BusinessRoleService
                roles = BusinessRoleService.create_business_roles(business)
                if is_owner:
                    role = roles.get("Admin")
                elif is_co_owner:
                    role = roles.get("Gerente")
                else:
                    role = roles.get("Viewer")
            
            # Cambiar el negocio activo
            request.user.business = business
            request.user.business_role = role
            request.user.save(update_fields=['business', 'business_role'])
            
            # Configurar el contexto del negocio y el esquema
            from config.middleware import set_current_business_id
            from app.business.services.business_service import DatabaseService
            
            set_current_business_id(business.id)
            
            # Verificar si el esquema existe y crearlo si no
            success, result = DatabaseService.verify_business_database(business.id)
            if not success:
                logger.info(f"Creando esquema para negocio {business.id}")
                schema_created = DatabaseService.create_business_database(business)
                if schema_created:
                    logger.info(f"✅ Esquema para negocio {business.id} creado exitosamente")
                else:
                    logger.warning(f"⚠️ No se pudo crear esquema para negocio {business.id}")
            
            # Cambiar al esquema del negocio
            DatabaseService.switch_to_business_schema(business.id)
            
            # Formatear nombre del negocio para la respuesta
            formatted_name = business.name.replace("_", " ").title()
            
            return Response({
                "message": f"Se ha cambiado al negocio: {formatted_name}",
                "business": {
                    "id": business.id,
                    "name": formatted_name,
                    "original_name": business.name
                },
                "role": role.name if role else None
            })
            
        except Business.DoesNotExist:
            logger.warning(f"Usuario {request.user.id} intentó acceder a negocio inexistente {business_id}")
            return Response({"error": "Negocio no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as e:
            logger.error(f"Error de validación en SwitchBusinessView para usuario {request.user.id}: {str(e)}")
            return Response({"error": "Datos inválidos proporcionados"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error inesperado en SwitchBusinessView para usuario {request.user.id}: {str(e)}", exc_info=True)
            return Response({"error": "Error interno del servidor"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # AGREGAR: Método OPTIONS para CORS
    def options(self, request, *args, **kwargs):
        """
        Maneja las peticiones OPTIONS para CORS
        """
        response = Response()
        response['Allow'] = 'POST, OPTIONS'
        return response