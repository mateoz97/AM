# app/orders/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging

from app.orders.models import Order, OrderStatusHistory

logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()


@receiver(post_save, sender=Order)
def order_saved(sender, instance, created, **kwargs):
    """Signal que se ejecuta cuando se guarda una orden"""
    try:
        business_id = instance.business.id
        
        # Grupos a notificar
        groups = [
            f"orders_business_{business_id}",
            f"orders_managers_{business_id}",
            f"orders_kitchen_{business_id}",
            f"orders_waiters_{business_id}"
        ]
        
        if created:
            # Nueva orden creada
            from app.orders.serializers import OrderSerializer
            order_data = OrderSerializer(instance).data
            
            for group in groups:
                async_to_sync(channel_layer.group_send)(
                    group,
                    {
                        'type': 'order_created',
                        'order_data': order_data
                    }
                )
            
            logger.info(f"Orden {instance.order_number} creada y notificada via WebSocket")
            
        else:
            # Orden actualizada
            from app.orders.serializers import OrderSerializer
            order_data = OrderSerializer(instance).data
            
            for group in groups:
                async_to_sync(channel_layer.group_send)(
                    group,
                    {
                        'type': 'order_updated',
                        'order_data': order_data
                    }
                )
            
            logger.info(f"Orden {instance.order_number} actualizada y notificada via WebSocket")
            
    except Exception as e:
        logger.error(f"Error en signal order_saved: {str(e)}", exc_info=True)


@receiver(post_save, sender=OrderStatusHistory)
def order_status_changed(sender, instance, created, **kwargs):
    """Signal que se ejecuta cuando cambia el estado de una orden"""
    if not created:
        return
    
    try:
        order = instance.order
        business_id = order.business.id
        
        # Grupos a notificar
        groups = [
            f"orders_business_{business_id}",
            f"orders_managers_{business_id}",
            f"orders_kitchen_{business_id}",
            f"orders_waiters_{business_id}"
        ]
        
        # Enviar notificación de cambio de estado
        for group in groups:
            async_to_sync(channel_layer.group_send)(
                group,
                {
                    'type': 'order_status_changed',
                    'order_id': str(order.id),
                    'order_number': order.order_number,
                    'old_status': instance.old_status,
                    'new_status': instance.new_status,
                    'new_status_display': order.get_status_display(),
                    'changed_by': instance.changed_by.get_full_name() if instance.changed_by else 'Sistema',
                    'timestamp': instance.timestamp.isoformat(),
                    'notes': instance.notes
                }
            )
        
        # Notificación especial para estados críticos
        if instance.new_status in ['ready', 'cancelled']:
            urgent_message = {
                'ready': f'¡Orden {order.order_number} está lista para servir!',
                'cancelled': f'Orden {order.order_number} ha sido cancelada'
            }
            
            for group in groups:
                async_to_sync(channel_layer.group_send)(
                    group,
                    {
                        'type': 'order_notification',
                        'notification_type': 'urgent',
                        'message': urgent_message[instance.new_status],
                        'order_id': str(order.id),
                        'urgent': True
                    }
                )
        
        logger.info(f"Cambio de estado de orden {order.order_number} notificado: {instance.old_status} → {instance.new_status}")
        
    except Exception as e:
        logger.error(f"Error en signal order_status_changed: {str(e)}", exc_info=True)


def send_order_delay_notification(order):
    """Función para enviar notificación de retraso en orden"""
    try:
        business_id = order.business.id
        
        groups = [
            f"orders_business_{business_id}",
            f"orders_managers_{business_id}",
            f"orders_waiters_{business_id}"
        ]
        
        message = f"⚠️ Orden {order.order_number} está retrasada"
        
        for group in groups:
            async_to_sync(channel_layer.group_send)(
                group,
                {
                    'type': 'order_notification',
                    'notification_type': 'delay',
                    'message': message,
                    'order_id': str(order.id),
                    'urgent': True
                }
            )
        
        logger.warning(f"Notificación de retraso enviada para orden {order.order_number}")
        
    except Exception as e:
        logger.error(f"Error enviando notificación de retraso: {str(e)}", exc_info=True)


def send_kitchen_notification(order, message):
    """Función para enviar notificación específica a cocina"""
    try:
        business_id = order.business.id
        
        kitchen_group = f"orders_kitchen_{business_id}"
        
        async_to_sync(channel_layer.group_send)(
            kitchen_group,
            {
                'type': 'order_notification',
                'notification_type': 'kitchen',
                'message': message,
                'order_id': str(order.id),
                'urgent': False
            }
        )
        
        logger.info(f"Notificación a cocina enviada para orden {order.order_number}: {message}")
        
    except Exception as e:
        logger.error(f"Error enviando notificación a cocina: {str(e)}", exc_info=True)