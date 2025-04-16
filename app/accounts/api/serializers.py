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