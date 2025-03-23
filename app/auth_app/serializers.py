from rest_framework import serializers
from auth_app.models import Business
from auth_app.services import RoleService  

class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = "__all__"

    def create(self, validated_data):
        business = Business.objects.create(**validated_data)
        RoleService.create_business_roles(business)  # Llama al servicio al crear un negocio
        return business
