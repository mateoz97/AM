# API views for managing user authentication, business roles, and permissions.
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action

# Models    
from app.business.models.business import Business

# Serializers
from app.business.api.serializers import BusinessSerializer

# Validators
import logging

logger = logging.getLogger(__name__)

class BusinessViewSet(viewsets.ModelViewSet):
    queryset = Business.objects.all()
    serializer_class = BusinessSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        # Guardar el negocio con el usuario actual como propietario
        business = serializer.save(owner=self.request.user)
        
        # Actualizar el usuario para asignarle el negocio creado
        self.request.user.business = business
        
        # Crear roles para el negocio
        from app.roles.services.role_service import BusinessRoleService
        roles = BusinessRoleService.create_business_roles(business)
        
        # Asignar rol de administrador al creador
        admin_role = roles.get("Admin") or roles.get("Administrador")
        if admin_role:
            self.request.user.business_role = admin_role
            self.request.user.save(update_fields=['business', 'business_role'])
        
        # Crear base de datos para el negocio - Asegurarse que esto se ejecute
        from app.business.services.business_service import DatabaseService
        print(f"Creando base de datos para negocio: {business.name} (ID: {business.id})")
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
        
        return Response(businesses_data)
            
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
        business_id = request.data.get('business_id')
        
        if not business_id:
            return Response({"error": "Se requiere ID de negocio"}, status=400)
        
        try:
            # Verificar que el usuario sea propietario o co-propietario del negocio
            business = Business.objects.get(id=business_id)
            
            is_owner = business.owner == request.user
            is_co_owner = request.user in business.co_owners.all()
            is_member = business.members.filter(id=request.user.id).exists()
            
            if not (is_owner or is_co_owner or is_member):
                return Response({"error": "No tienes acceso a este negocio"}, status=403)
            
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
            
            # Configurar la base de datos para el negocio si no existe
            from config.middleware import set_current_business_id
            set_current_business_id(business.id)
            
            # Verificar si la base de datos existe y crearla si no
            from django.conf import settings
            db_name = f'business_{business.id}'
            if db_name not in settings.DATABASES:
                from app.business.services.business_service import DatabaseService
                DatabaseService.create_business_database(business)
            
            return Response({
                "message": f"Se ha cambiado al negocio: {business.name}",
                "business": {
                    "id": business.id,
                    "name": business.name
                },
                "role": role.name if role else None
            })
            
        except Business.DoesNotExist:
            return Response({"error": "Negocio no encontrado"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=400)