from rest_framework import serializers
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
    role = serializers.CharField(write_only=True, required=False)  # Opcional
    business = serializers.PrimaryKeyRelatedField(
        queryset=Business.objects.all(), allow_null=True, required=False
    )  # Permitir None

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "role", "business"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        role_name = validated_data.pop("role", None)
        business = validated_data.pop("business", None)
        user = User.objects.create_user(**validated_data)

        if business:
            user.business = business
            user.save()

        if role_name and business:
            try:
                role = Group.objects.get(name=f"{business.name}_{role_name}")
                user.role = role
                user.groups.add(role)
                user.save()
            except Group.DoesNotExist:
                raise serializers.ValidationError("Rol no válido.")

        return user
