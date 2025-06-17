# app/settings/utils.py
from django.utils import timezone


class SettingsUtils:
    """
    Utilidades para configuraciones
    """
    
    @staticmethod
    def should_logout_user(user):
        """
        Verificar si un usuario debería ser deslogueado por inactividad
        """
        if not hasattr(user, 'business') or not user.business:
            return False
        
        try:
            business_settings = user.business.business_settings
            auto_logout_time = business_settings.auto_logout_time
            
            if auto_logout_time <= 0:
                return False
            
            # Verificar última actividad del usuario
            # Esto requeriría un sistema de tracking de actividad
            # Por ahora es un placeholder
            
            return False
            
        except Exception:
            return False
    
    @staticmethod
    def get_user_theme_preferences(user):
        """
        Obtener preferencias de tema del usuario
        """
        try:
            user_settings = user.user_settings
            return {
                'theme': user_settings.theme,
                'font_size': user_settings.font_size,
                'compact_mode': user_settings.compact_mode,
                'language': user_settings.language,
            }
        except AttributeError:
            return {
                'theme': 'light',
                'font_size': 'medium',
                'compact_mode': False,
                'language': 'es',
            }
    
    @staticmethod
    def get_notification_preferences(user):
        """
        Obtener preferencias de notificación del usuario
        """
        try:
            user_settings = user.user_settings
            return {
                'notifications_enabled': user_settings.notifications_enabled,
                'email_notifications': user_settings.email_notifications,
                'order_updates': user_settings.order_updates,
                'inventory_alerts': user_settings.inventory_alerts,
                'system_notifications': user_settings.system_notifications,
            }
        except AttributeError:
            return {
                'notifications_enabled': True,
                'email_notifications': True,
                'order_updates': True,
                'inventory_alerts': True,
                'system_notifications': True,
            }
    
    @staticmethod
    def validate_business_settings_compatibility(settings_data):
        """
        Validar compatibilidad entre configuraciones de negocio
        """
        errors = []
        
        # Validar tiempos de sesión
        auto_logout = settings_data.get('auto_logout_time', 30)
        session_timeout = settings_data.get('session_timeout', 60)
        
        if auto_logout >= session_timeout:
            errors.append(
                "El tiempo de auto logout debe ser menor al timeout de sesión"
            )
        
        # Validar configuraciones de servicio
        table_service = settings_data.get('enable_table_service', True)
        takeaway = settings_data.get('enable_takeaway', True)
        delivery = settings_data.get('enable_delivery', False)
        
        if not any([table_service, takeaway, delivery]):
            errors.append(
                "Debe habilitar al menos un tipo de servicio"
            )
        
        return errors


class SettingsCache:
    """
    Cache para configuraciones frecuentemente accedidas
    """
    
    _user_settings_cache = {}
    _business_settings_cache = {}
    
    @classmethod
    def get_user_settings(cls, user_id):
        """
        Obtener configuraciones de usuario desde cache
        """
        cache_key = f"user_settings_{user_id}"
        
        if cache_key not in cls._user_settings_cache:
            try:
                from app.settings.models import UserSettings
                settings = UserSettings.objects.get(user_id=user_id)
                cls._user_settings_cache[cache_key] = {
                    'theme': settings.theme,
                    'language': settings.language,
                    'notifications_enabled': settings.notifications_enabled,
                    'cached_at': timezone.now()
                }
            except UserSettings.DoesNotExist:
                cls._user_settings_cache[cache_key] = None
        
        return cls._user_settings_cache[cache_key]
    
    @classmethod
    def invalidate_user_cache(cls, user_id):
        """
        Invalidar cache de configuraciones de usuario
        """
        cache_key = f"user_settings_{user_id}"
        if cache_key in cls._user_settings_cache:
            del cls._user_settings_cache[cache_key]
    
    @classmethod
    def get_business_settings(cls, business_id):
        """
        Obtener configuraciones de negocio desde cache
        """
        cache_key = f"business_settings_{business_id}"
        
        if cache_key not in cls._business_settings_cache:
            try:
                from app.settings.models import BusinessSettings
                settings = BusinessSettings.objects.get(business_id=business_id)
                cls._business_settings_cache[cache_key] = {
                    'auto_logout_time': settings.auto_logout_time,
                    'require_two_factor': settings.require_two_factor,
                    'low_stock_threshold': settings.low_stock_threshold,
                    'cached_at': timezone.now()
                }
            except BusinessSettings.DoesNotExist:
                cls._business_settings_cache[cache_key] = None
        
        return cls._business_settings_cache[cache_key]
    
    @classmethod
    def invalidate_business_cache(cls, business_id):
        """
        Invalidar cache de configuraciones de negocio
        """
        cache_key = f"business_settings_{business_id}"
        if cache_key in cls._business_settings_cache:
            del cls._business_settings_cache[cache_key]