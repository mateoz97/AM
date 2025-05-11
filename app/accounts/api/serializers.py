# Django REST Framework
from rest_framework import serializers

# Django
from django.contrib.auth import authenticate

# Modesls and services
from app.business.models.business import Business
from app.accounts.models.user import CustomUser
from app.roles.models.role import BusinessRole


class UserSerializer(serializers.ModelSerializer):
    business_role = serializers.PrimaryKeyRelatedField(
        queryset=BusinessRole.objects.all(), required=False, allow_null=True
    )
    business = serializers.PrimaryKeyRelatedField(
        queryset=Business.objects.all(), required=False, allow_null=True
    )

    business_info = serializers.SerializerMethodField()
    role_info = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomUser
        fields = ["id", "username", "password", "email", "business_role", "business", "first_name", "last_name","business_info", "role_info"]
        extra_kwargs = {"password": {"write_only": True}}
        read_only_fields = ["business_info", "role_info"]  
        
    def get_business_info(self, obj):
        """Devuelve información detallada del negocio del usuario"""
        if obj.business:
            return {
                'id': obj.business.id,
                'name': obj.business.name,
                'description': obj.business.description,
                'is_active': obj.business.is_active,
                'owner_id': obj.business.owner.id if obj.business.owner else None,
                'is_owner': obj.business.owner == obj if obj.business.owner else False
            }
        return None
    
    def get_role_info(self, obj):
        """Devuelve información detallada del rol del usuario"""
        if obj.business_role:
            # Incluir los permisos del rol
            permissions = {}
            if hasattr(obj.business_role, 'role_permissions'):
                role_perms = obj.business_role.role_permissions
                for field in role_perms._meta.get_fields():
                    if field.name.startswith('can_'):
                        permissions[field.name] = getattr(role_perms, field.name)
            
            return {
                'id': obj.business_role.id,
                'name': obj.business_role.name,
                'description': obj.business_role.description,
                'is_default': obj.business_role.is_default,
                'can_modify': obj.business_role.can_modify,
                'permissions': permissions
            }
        return None

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
                    from app.accounts.services import BusinessRoleService
                    roles = BusinessRoleService.create_default_roles(business)
                    user.business_role = roles.get("viewer")

        user.save()
        
        return user

    def get_role(self, obj):
        return obj.business_role.name if obj.business_role else None

    def get_business_role_instance(self, role_name, business=None):
        """
        Obtiene o crea un rol de negocio basado en el nombre.
        
        Args:
            role_name (str): Nombre del rol
            business (Business): Instancia del negocio (obligatorio)
            
        Returns:
            BusinessRole: Instancia del rol o None si no se pudo crear
        """
        if not business:
            return None
            
        try:
            # Primero intentar obtener un rol existente
            role = BusinessRole.objects.get(
                business=business,
                name=role_name
            )
            return role
        except BusinessRole.DoesNotExist:
            # Si no existe, intentar crearlo con valores predeterminados
            try:
                role = BusinessRole.objects.create(
                    business=business,
                    name=role_name,
                    description=f"Rol {role_name} creado automáticamente",
                    is_default=False,
                    can_modify=True
                )
                return role
            except Exception:
                # Si hay algún error, retornar None
                return None

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
    
    def to_representation(self, instance):
        """Sobrescribir para incluir información adicional"""
        data = super().to_representation(instance)
        
        # Remover campos que no queremos mostrar en la respuesta
        data.pop('business', None)
        data.pop('business_role', None)
        
        return data

class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(required=True)  # Puede ser username o email
    password = serializers.CharField(write_only=True, required=True)

    def validate(self, data):
        identifier = data.get("identifier")
        password = data.get("password")
        
        if not identifier or not password:
            raise serializers.ValidationError("Se requiere username/email y contraseña")
        
        # Buscar usuario por email o username
        user = CustomUser.objects.filter(email=identifier).first()
        if not user:
            user = CustomUser.objects.filter(username=identifier).first()
        
        if not user:
            raise serializers.ValidationError("Usuario no encontrado")
        
        # Autenticar con username (Django requiere username para authenticate)
        user = authenticate(username=user.username, password=password)
        
        if not user:
            raise serializers.ValidationError("Credenciales inválidas")
        
        return {"user": user}
