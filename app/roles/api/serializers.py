# Django REST Framework
from rest_framework import serializers

# Modesls and services
from app.roles.models.role import RolePermission, BusinessRole



class RolePermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RolePermission
        exclude = ['id', 'business_role', 'created_at', 'updated_at']
        

class BusinessRoleSerializer(serializers.ModelSerializer):
    role_permissions = RolePermissionSerializer(read_only=True)
    
    class Meta:
        model = BusinessRole
        fields = ['id', 'name', 'description', 'is_default', 'can_modify', 'created_at', 'role_permissions']
        read_only_fields = ['is_default', 'can_modify', 'created_at']

    def create(self, validated_data):
        business = self.context.get('business')
        if not business:
            raise serializers.ValidationError("Se requiere un negocio para crear un rol")
            
        role = BusinessRole.objects.create(
            business=business,
            **validated_data
        )
        return role

class BusinessRoleUpdateSerializer(serializers.ModelSerializer):
    role_permissions = RolePermissionSerializer()
    
    class Meta:
        model = BusinessRole
        fields = ['name', 'description', 'role_permissions']
        
    def validate(self, data):
        instance = getattr(self, 'instance', None)
        if instance and not instance.can_modify:
            raise serializers.ValidationError("Este rol no puede ser modificado")
        return data
        
    def update(self, instance, validated_data):
        permissions_data = validated_data.pop('role_permissions', {})
        
        # Actualizar campos básicos del rol
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description', instance.description)
        instance.save()
        
        # Actualizar permisos si se proporcionaron
        if permissions_data:
            permissions = instance.role_permissions
            for attr, value in permissions_data.items():
                setattr(permissions, attr, value)
            permissions.save()
            
        return instance
  