from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import Business
from .services import RoleService  
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = "__all__"

    def create(self, validated_data):
        business = Business.objects.create(**validated_data)
        RoleService.create_business_roles(business)
        return business
    
User = get_user_model()
    
class UserSerializer(serializers.ModelSerializer):
    role = serializers.CharField(write_only=True, required=False, allow_null=True)
    business = serializers.PrimaryKeyRelatedField(
    queryset=Business.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = User
        fields = ["id", "username", "password", "email","role","business"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        role_name = validated_data.pop("role", None)
        business = validated_data.pop("business", None)

        # Crear usuario sin rol ni negocio
        user = User.objects.create_user(**validated_data)

        # Asignar negocio si se proporciona
        if business:
            user.business = business

            # Si se une a un negocio, darle rol de Mesero
            try:
                mesero_role = Group.objects.get(name=f"{business.name}_Mesero")
                user.role = mesero_role
                user.groups.add(mesero_role)
            except Group.DoesNotExist:
                raise serializers.ValidationError("Rol no válido.")

        user.save()
        
        return user

    def get_role(self, obj):
        return obj.role.name if obj.role else None

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
                user = User.objects.get(email=email)
                username = user.username  # Obtener el username para autenticación
            except User.DoesNotExist:
                raise serializers.ValidationError("Usuario no encontrado")
        
        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError("Credenciales inválidas")
        
        return {"user": user}
