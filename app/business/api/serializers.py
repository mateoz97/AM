# Django REST Framework
from rest_framework import serializers

# Modesls and services
from app.business.models.business import Business, BusinessJoinRequest, BusinessInvitation
# Services
from app.roles.services.role_service import RoleService  



class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = "__all__"

    def create(self, validated_data):
        business = Business.objects.create(**validated_data)
        
        # Mantener compatibilidad con el sistema anterior
        RoleService.create_business_roles(business)
        
        # Crear roles personalizados para el nuevo negocio
        from app.business.services.business_service import BusinessRoleService
        roles = BusinessRoleService.create_default_roles(business)
        
        # Si hay un propietario, asignarle el rol de Administrador
        if business.owner:
            admin_role = roles.get("Admin")
            if admin_role:
                business.owner.business_role = admin_role
                business.owner.save(update_fields=['business_role'])
        
        return business
    
    def get_queryset(self):
        return Business.objects.filter(is_active=True)
    
    def delete(self, using=None, keep_parents=False):
        """Sobrescribe el método delete para hacer un borrado lógico"""
        self.is_active = False
        self.save()
        return (1, {})
    
    def deactivate(self):
        """Desactiva el negocio sin eliminarlo"""
        self.is_active = False
        self.save()
    
    def reactivate(self):
        """Reactiva un negocio previamente desactivado"""
        self.is_active = True
        self.save()
    
class BusinessJoinRequestSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    business_name = serializers.SerializerMethodField()
    
    class Meta:
        model = BusinessJoinRequest
        fields = ['id', 'user', 'user_name', 'business', 'business_name', 'status', 'message', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'business', 'created_at', 'updated_at']
        
    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
        
    def get_business_name(self, obj):
        return obj.business.name

class BusinessInvitationSerializer(serializers.ModelSerializer):
    business_name = serializers.SerializerMethodField()
    role_name = serializers.SerializerMethodField()
    is_valid = serializers.SerializerMethodField()
    
    class Meta:
        model = BusinessInvitation
        fields = ['id', 'business', 'business_name', 'token', 'expires_at', 'role', 'role_name', 'used', 'created_at', 'is_valid']
        read_only_fields = ['id', 'business', 'token', 'created_at']
        
    def get_business_name(self, obj):
        return obj.business.name
    
    def get_role_name(self, obj):
        if obj.role:
            return obj.role.name
        return None
    
    def get_is_valid(self, obj):
        return obj.is_valid()