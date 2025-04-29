# Django REST Framework
from rest_framework import serializers

# Models and services
from app.business.models.business import Business, BusinessJoinRequest, BusinessInvitation

class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = ["id", "name", "owner", "is_active", "description", "address", 
                 "phone", "email", "website", "created_at", "updated_at"]
        read_only_fields = ["owner", "created_at", "updated_at"]

    def create(self, validated_data):
        business = Business.objects.create(**validated_data)
        
        # Ya no es necesario crear roles aquí porque se hace en el modelo Business.save()
        # y en la vista BusinessViewSet.perform_create
        
        return business
    
    def get_queryset(self):
        return Business.objects.filter(is_active=True)
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        # Añadir el número de miembros
        representation['member_count'] = instance.members.count() if hasattr(instance, 'members') else 0
        
        # Añadir información del propietario
        if instance.owner:
            representation['owner_name'] = instance.owner.get_full_name() or instance.owner.username
            representation['owner_email'] = instance.owner.email
        
        return representation
    
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
    created_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = BusinessInvitation
        fields = ['id', 'business', 'business_name', 'token', 'expires_at', 
                 'role', 'role_name', 'used', 'created_at', 'is_valid', 
                 'created_by', 'created_by_name']
        read_only_fields = ['id', 'business', 'token', 'created_at', 'created_by']
        
    def get_business_name(self, obj):
        return obj.business.name
    
    def get_role_name(self, obj):
        if obj.role:
            return obj.role.name
        return None
    
    def get_is_valid(self, obj):
        return obj.is_valid()
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None