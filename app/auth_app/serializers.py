from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import Business
from .services import RoleService  
from .models import CustomUser
from django.contrib.auth.models import Group
from .models import BusinessRole, RolePermission



class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = "__all__"

    def create(self, validated_data):
        business = Business.objects.create(**validated_data)
        
        # Mantener compatibilidad con el sistema anterior
        RoleService.create_business_roles(business)
        
        # Crear roles personalizados para el nuevo negocio
        from .services import BusinessRoleService
        roles = BusinessRoleService.create_default_roles(business)
        
        # Si hay un propietario, asignarle el rol de Administrador
        if business.owner:
            admin_role = roles.get("Administrador")
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

    
class UserSerializer(serializers.ModelSerializer):
    business_role = serializers.PrimaryKeyRelatedField(
        queryset=BusinessRole.objects.all(), required=False, allow_null=True
    )
    business = serializers.PrimaryKeyRelatedField(
        queryset=Business.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = CustomUser
        fields = ["id", "username", "password", "email", "business_role", "business", "first_name", "last_name"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        role_id = validated_data.pop("business_role", None)
        business = validated_data.pop("business", None)

        # Crear usuario sin rol ni negocio
        user = CustomUser.objects.create_user(**validated_data)

        if business:
            user.business = business
            # Si se especificó un rol, asignarlo
            if role_id:
                user.business_role = role_id
            else:
                # Buscar rol de visualizador para asignar por defecto
                try:
                    default_role = BusinessRole.objects.get(business=business, is_default=True, name="admin")
                    user.business_role = default_role
                except BusinessRole.DoesNotExist:
                    # Si no existe el rol, crear roles por defecto
                    from .services import BusinessRoleService
                    roles = BusinessRoleService.create_default_roles(business)
                    user.business_role = roles.get("viewer")

        user.save()
        
        return user

    def get_role(self, obj):
        return obj.business_role.name if obj.business_role else None

    def get_role_instance(self, role_name):
        role, created = Group.objects.get_or_create(name=role_name)
        return role

    def get_business(self, obj):
        return obj.business.name if obj.business else None
    
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

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    username = serializers.CharField(required=False)
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get("email")
        username = data.get("username")
        password = data.get("password")
        
        if not username and not email:
            raise serializers.ValidationError("Se requiere username o email")
        
        if email and not username:
            try:
                user = CustomUser.objects.get(email=email)
                username = user.username  # Obtener el username para autenticación
            except CustomUser.DoesNotExist:
                raise serializers.ValidationError("Usuario no encontrado")
        
        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError("Credenciales inválidas")
        
        return {"user": user}

class RolePermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RolePermission
        exclude = ['id', 'role', 'created_at', 'updated_at']


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