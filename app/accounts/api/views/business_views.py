# API views for managing user authentication, business roles, and permissions.
from rest_framework import viewsets, permissions

# Models    
from app.accounts.models.business import Business

# Serializers
from app.accounts.api.serializers import BusinessSerializer

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
        from app.accounts.services.role_service import BusinessRoleService
        roles = BusinessRoleService.create_default_roles(business)
        
        # Asignar rol de administrador al creador
        admin_role = roles.get("Admin") or roles.get("Administrador")
        if admin_role:
            self.request.user.business_role = admin_role
            self.request.user.save(update_fields=['business', 'business_role'])
        
        # Crear base de datos para el negocio - Asegurarse que esto se ejecute
        print(f"Creando base de datos para negocio: {business.name} ({business.id})")
        from app.accounts.services.business_service import DatabaseService
        success = DatabaseService.create_business_database(business)
        
        if not success:
            print(f"Advertencia: No se pudo crear la base de datos para el negocio {business.name}")