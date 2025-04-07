from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import Business
from .services import RoleService  
from .models import CustomUser
from django.contrib.auth.models import Group



class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = "__all__"

    def create(self, validated_data):
        business = Business.objects.create(**validated_data)
        RoleService.create_business_roles(business)
        return business
    

    
class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    business = serializers.PrimaryKeyRelatedField(
        queryset=Business.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = CustomUser
        fields = ["id", "username", "password", "email", "role", "business"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        role_name = validated_data.pop("role", None)
        business = validated_data.pop("business", None)

        # Crear usuario sin rol ni negocio
        user = CustomUser.objects.create_user(**validated_data)

        if business:
            user.business = business
            # Usar role_name o un rol por defecto
            role = self.get_role_instance(role_name or 'Visualizador')
            user.role = role
            user.groups.add(role)
        else:
            # Usar role_name o un rol por defecto
            role = self.get_role_instance(role_name or 'Administrador')
            user.role = role
            user.groups.add(role)

        user.save()
        
        return user

    def get_role(self, obj):
        return obj.role.name if obj.role else None

    def get_role_instance(self, role_name):
        role, created = Group.objects.get_or_create(name=role_name)
        return role

    def get_business(self, obj):
        return obj.business.name if obj.business else None

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
