# app/settings/services.py
from django.db import transaction
from django.contrib.auth import get_user_model
from app.settings.models import UserSettings, BusinessSettings, NotificationTemplate

User = get_user_model()


class SettingsService:
    """
    Servicio para operaciones complejas de configuraciones
    """
    
    @staticmethod
    def reset_user_settings_to_defaults(user_settings):
        """
        Resetear configuraciones de usuario a valores por defecto
        """
        with transaction.atomic():
            # Guardar configuraciones importantes antes del reset
            user = user_settings.user
            
            # Aplicar valores por defecto
            user_settings.theme = 'light'
            user_settings.language = 'es'
            user_settings.font_size = 'medium'
            user_settings.compact_mode = False
            user_settings.notifications_enabled = True
            user_settings.email_notifications = True
            user_settings.order_updates = True
            user_settings.inventory_alerts = True
            user_settings.system_notifications = True
            user_settings.profile_visible = True
            user_settings.show_activity = False
            user_settings.allow_messages = True
            
            user_settings.save()
            return user_settings
    
    @staticmethod
    def reset_business_settings_to_defaults(business_settings):
        """
        Resetear configuraciones de negocio a valores por defecto
        """
        with transaction.atomic():
            business_settings.auto_logout_time = 30
            business_settings.session_timeout = 60
            business_settings.require_two_factor = False
            business_settings.allow_customer_registration = True
            business_settings.require_order_confirmation = True
            business_settings.enable_table_service = True
            business_settings.enable_takeaway = True
            business_settings.enable_delivery = False
            business_settings.low_stock_threshold = 5
            business_settings.auto_deduct_inventory = True
            business_settings.daily_report_time = None
            business_settings.weekly_report_day = 1
            
            business_settings.save()
            return business_settings
    
    @staticmethod
    def create_default_notification_templates(business):
        """
        Crear plantillas de notificación por defecto para un negocio
        """
        default_templates = [
            {
                'notification_type': 'order_created',
                'title': '🆕 Nuevo Pedido #{order_id}',
                'message': 'Se ha creado un nuevo pedido para la mesa {table_number}. Total: ${total_amount}'
            },
            {
                'notification_type': 'order_confirmed',
                'title': '✅ Pedido Confirmado #{order_id}',
                'message': 'El pedido de la mesa {table_number} ha sido confirmado y enviado a cocina.'
            },
            {
                'notification_type': 'order_ready',
                'title': '🍽️ Pedido Listo #{order_id}',
                'message': 'El pedido de la mesa {table_number} está listo para servir.'
            },
            {
                'notification_type': 'order_delivered',
                'title': '🎉 Pedido Entregado #{order_id}',
                'message': 'El pedido de la mesa {table_number} ha sido entregado al cliente.'
            },
            {
                'notification_type': 'low_stock',
                'title': '⚠️ Stock Bajo: {product_name}',
                'message': 'El producto {product_name} tiene stock bajo ({current_stock} unidades). Considera reabastecer.'
            },
            {
                'notification_type': 'user_joined',
                'title': '👋 Nuevo Usuario',
                'message': '{user_name} se ha unido al equipo con el rol de {role_name}.'
            },
            {
                'notification_type': 'daily_report',
                'title': '📊 Reporte Diario - {date}',
                'message': 'Ventas del día: ${daily_sales}. Pedidos procesados: {orders_count}. Ver reporte completo.'
            }
        ]
        
        templates_created = 0
        
        with transaction.atomic():
            for template_data in default_templates:
                template, created = NotificationTemplate.objects.get_or_create(
                    business=business,
                    notification_type=template_data['notification_type'],
                    defaults={
                        'title': template_data['title'],
                        'message': template_data['message'],
                        'is_active': True
                    }
                )
                if created:
                    templates_created += 1
        
        return templates_created
    
    @staticmethod
    def export_user_settings(user):
        """
        Exportar todas las configuraciones de un usuario
        """
        from app.settings.api.serializers import (
            UserSettingsSerializer, 
            BusinessSettingsSerializer
        )
        
        export_data = {
            'user_info': {
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            },
            'export_date': timezone.now().isoformat(),
        }
        
        # Configuraciones de usuario
        try:
            user_settings = UserSettings.objects.get(user=user)
            export_data['user_settings'] = UserSettingsSerializer(user_settings).data
        except UserSettings.DoesNotExist:
            export_data['user_settings'] = None
        
        # Configuraciones de negocio
        if user.business:
            try:
                business_settings = BusinessSettings.objects.get(business=user.business)
                export_data['business_settings'] = BusinessSettingsSerializer(business_settings).data
            except BusinessSettings.DoesNotExist:
                export_data['business_settings'] = None
            
            export_data['business_info'] = {
                'name': user.business.name,
                'description': user.business.description,
            }
        else:
            export_data['business_settings'] = None
            export_data['business_info'] = None
        
        return export_data
    
    @staticmethod
    def apply_business_settings_to_users(business, settings_update):
        """
        Aplicar configuraciones de negocio a todos los usuarios del negocio
        """
        users = User.objects.filter(business=business)
        updated_count = 0
        
        with transaction.atomic():
            for user in users:
                user_settings, created = UserSettings.objects.get_or_create(user=user)
                
                # Aplicar configuraciones específicas si es necesario
                if 'force_theme' in settings_update:
                    user_settings.theme = settings_update['force_theme']
                
                if 'force_notifications' in settings_update:
                    user_settings.notifications_enabled = settings_update['force_notifications']
                
                user_settings.save()
                updated_count += 1
        
        return updated_count
    
    @staticmethod
    def get_business_settings_summary(business):
        """
        Obtener resumen de configuraciones del negocio
        """
        try:
            business_settings = BusinessSettings.objects.get(business=business)
            
            summary = {
                'security': {
                    'auto_logout_enabled': business_settings.auto_logout_time > 0,
                    'two_factor_required': business_settings.require_two_factor,
                    'session_timeout_minutes': business_settings.session_timeout,
                },
                'operations': {
                    'customer_registration': business_settings.allow_customer_registration,
                    'table_service': business_settings.enable_table_service,
                    'takeaway': business_settings.enable_takeaway,
                    'delivery': business_settings.enable_delivery,
                },
                'inventory': {
                    'low_stock_threshold': business_settings.low_stock_threshold,
                    'auto_deduct': business_settings.auto_deduct_inventory,
                },
                'notifications': {
                    'templates_count': NotificationTemplate.objects.filter(
                        business=business, is_active=True
                    ).count(),
                }
            }
            
            return summary
            
        except BusinessSettings.DoesNotExist:
            return None


class NotificationService:
    """
    Servicio para gestión de notificaciones basadas en plantillas
    """
    
    @staticmethod
    def render_notification_template(template, context_data):
        """
        Renderizar una plantilla de notificación con datos del contexto
        """
        try:
            title = template.title.format(**context_data)
            message = template.message.format(**context_data)
            
            return {
                'title': title,
                'message': message,
                'type': template.notification_type,
                'template_id': template.id
            }
        except KeyError as e:
            raise ValueError(f"Falta el parámetro {e} en el contexto")
        except Exception as e:
            raise ValueError(f"Error al renderizar plantilla: {str(e)}")
    
    @staticmethod
    def send_business_notification(business, notification_type, context_data, target_users=None):
        """
        Enviar notificación usando plantilla del negocio
        """
        try:
            template = NotificationTemplate.objects.get(
                business=business,
                notification_type=notification_type,
                is_active=True
            )
            
            notification_data = NotificationService.render_notification_template(
                template, context_data
            )
            
            # Aquí se integraría con el sistema de notificaciones real
            # Por ahora solo retornamos los datos renderizados
            
            return notification_data
            
        except NotificationTemplate.DoesNotExist:
            # Si no existe plantilla, usar mensaje por defecto
            return {
                'title': f'Notificación: {notification_type}',
                'message': 'Se ha producido un evento en el sistema',
                'type': notification_type,
                'template_id': None
            }