# API views for managing user authentication, business roles, and permissions.
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

# Models 
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
        business = serializer.save(owner=self.request.user)
        self.request.user.business = business
        
        # Crear roles para el negocio
        from app.roles.services.role_service import BusinessRoleService
        roles = BusinessRoleService.create_default_roles(business)
        
        # Asignar rol de administrador al creador
        admin_role = roles.get("Admin") or roles.get("Administrador")
        if admin_role:
            self.request.user.business_role = admin_role
            self.request.user.save(update_fields=['business', 'business_role'])
        
        # Crear base de datos para el negocio - Asegurarse que esto se ejecute
        print(f"Creando base de datos para negocio: {business.name} ({business.id})")
        from app.business.services.business_service import DatabaseService
        success = DatabaseService.create_business_database(business)
        
        if not success:
            print(f"Advertencia: No se pudo crear la base de datos para el negocio {business.name}")
            
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
                name="Viewer",
                is_default=True
            ).first()
            
            if not default_role:
                # Si no hay roles, crearlos
                from app.roles.services.role_service import BusinessRoleService
                roles_dict = BusinessRoleService.create_business_roles(business)
                default_role = roles_dict.get("Viewer")

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
    
    # app/business/api/views/business_views.py
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
            
            if not business.is_owner(request.user) and not business.members.filter(id=request.user.id).exists():
                return Response({"error": "No tienes acceso a este negocio"}, status=403)
            
            # Buscar el rol apropiado
            if business.owner == request.user:
                from app.roles.services.role_service import BusinessRoleService
                role = BusinessRoleService.objects.filter(business=business, name="Admin").first()
            else:
                # Si es co-propietario pero no hay un rol específico, usar el actual
                role = request.user.business_role
                
                # Si no tiene un rol en este negocio, asignarle uno apropiado
                if not role or role.business.id != business.id:
                    from app.roles.services.role_service import BusinessRoleService
                    role = BusinessRoleService.objects.filter(
                        business=business,
                        name__in=["Co-owner", "Admin", "Viewer"]
                    ).first()
            
            # Cambiar el negocio activo
            request.user.business = business
            if role:
                request.user.business_role = role
            request.user.save(update_fields=['business', 'business_role'])
            
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