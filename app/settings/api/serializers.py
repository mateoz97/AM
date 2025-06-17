# app/settings/api/serializers.py
from rest_framework import serializers
from app.settings.models import UserSettings, BusinessSettings, NotificationTemplate


class UserSettingsSerializer(serializers.ModelSerializer):
    """
    Serializer para configuraciones de usuario
    """
    user_info = serializers.SerializerMethodField()
    
    class Meta:
        model = UserSettings
        fields = [
            'id', 'user', 'user_info',
            # Apariencia
            'theme', 'language', 'font_size', 'compact_mode',
            # Notificaciones
            'notifications_enabled', 'email_notifications',
            'order_updates', 'inventory_alerts', 'system_notifications',
            # Privacidad
            'profile_visible', 'show_activity', 'allow_messages',
            # Metadatos
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
    
    def get_user_info(self, obj):
        """Información básica del usuario"""
        return {
            'id': obj.user.id,
            'username': obj.user.username,
            'email': obj.user.email,
            'first_name': obj.user.first_name,
            'last_name': obj.user.last_name,
        }
    
    def validate(self, data):
        """Validaciones personalizadas"""
        # Validar que si las notificaciones están deshabilitadas,
        # todas las sub-notificaciones también lo estén
        if not data.get('notifications_enabled', True):
            notification_fields = [
                'email_notifications', 'order_updates', 
                'inventory_alerts', 'system_notifications'
            ]
            for field in notification_fields:
                if data.get(field, False):
                    data[field] = False
        
        return data


class BusinessSettingsSerializer(serializers.ModelSerializer):
    """
    Serializer para configuraciones de negocio
    """
    business_info = serializers.SerializerMethodField()
    created_by_info = serializers.SerializerMethodField()
    
    class Meta:
        model = BusinessSettings
        fields = [
            'id', 'business', 'business_info',
            # Seguridad
            'auto_logout_time', 'session_timeout', 'require_two_factor',
            # Operativas
            'allow_customer_registration', 'require_order_confirmation',
            'enable_table_service', 'enable_takeaway', 'enable_delivery',
            # Inventario
            'low_stock_threshold', 'auto_deduct_inventory',
            # Reportes
            'daily_report_time', 'weekly_report_day',
            # Metadatos
            'created_by', 'created_by_info', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'business', 'created_by', 'created_at', 'updated_at']
    
    def get_business_info(self, obj):
        """Información básica del negocio"""
        return {
            'id': obj.business.id,
            'name': obj.business.name,
            'description': obj.business.description,
        }
    
    def get_created_by_info(self, obj):
        """Información del usuario que creó la configuración"""
        if obj.created_by:
            return {
                'id': obj.created_by.id,
                'username': obj.created_by.username,
                'first_name': obj.created_by.first_name,
                'last_name': obj.created_by.last_name,
            }
        return None
    
    def validate_auto_logout_time(self, value):
        """Validar tiempo de auto logout"""
        if value < 5 or value > 480:  # Entre 5 minutos y 8 horas
            raise serializers.ValidationError(
                "El tiempo de auto logout debe estar entre 5 y 480 minutos"
            )
        return value
    
    def validate_session_timeout(self, value):
        """Validar timeout de sesión"""
        if value < 15 or value > 720:  # Entre 15 minutos y 12 horas
            raise serializers.ValidationError(
                "El timeout de sesión debe estar entre 15 y 720 minutos"
            )
        return value
    
    def validate_low_stock_threshold(self, value):
        """Validar umbral de stock bajo"""
        if value < 0 or value > 1000:
            raise serializers.ValidationError(
                "El umbral de stock debe estar entre 0 y 1000"
            )
        return value


class NotificationTemplateSerializer(serializers.ModelSerializer):
    """
    Serializer para plantillas de notificación
    """
    business_info = serializers.SerializerMethodField()
    notification_type_display = serializers.CharField(
        source='get_notification_type_display', 
        read_only=True
    )
    
    class Meta:
        model = NotificationTemplate
        fields = [
            'id', 'business', 'business_info',
            'notification_type', 'notification_type_display',
            'title', 'message', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'business', 'created_at', 'updated_at']
    
    def get_business_info(self, obj):
        """Información básica del negocio"""
        return {
            'id': obj.business.id,
            'name': obj.business.name,
        }
    
    def validate_title(self, value):
        """Validar título"""
        if len(value.strip()) < 3:
            raise serializers.ValidationError(
                "El título debe tener al menos 3 caracteres"
            )
        return value.strip()
    
    def validate_message(self, value):
        """Validar mensaje"""
        if len(value.strip()) < 10:
            raise serializers.ValidationError(
                "El mensaje debe tener al menos 10 caracteres"
            )
        return value.strip()


class SettingsSummarySerializer(serializers.Serializer):
    """
    Serializer para resumen de todas las configuraciones
    """
    user_settings = UserSettingsSerializer(read_only=True)
    business_settings = BusinessSettingsSerializer(read_only=True)
    notification_templates_count = serializers.IntegerField(read_only=True)
    has_business = serializers.BooleanField(read_only=True)
    is_business_owner = serializers.BooleanField(read_only=True)