# app/orders/tasks.py
"""
Tareas en segundo plano para el sistema de órdenes.
Estas tareas se pueden ejecutar con Celery en producción.
"""
import logging
from datetime import timedelta
from django.utils import timezone
from django.core.management.base import BaseCommand

from app.orders.models import Order, OrderStatus
from app.orders.signals import send_order_delay_notification, send_kitchen_notification

logger = logging.getLogger(__name__)


def check_overdue_orders():
    """
    Verifica órdenes que están atrasadas y envía notificaciones.
    Esta función se puede ejecutar cada 5 minutos como tarea de fondo.
    """
    try:
        # Obtener órdenes que están en preparación hace más tiempo del estimado
        overdue_orders = Order.objects.filter(
            status=OrderStatus.PREPARING,
            started_at__isnull=False,
            estimated_preparation_time__isnull=False
        ).extra(
            where=["NOW() - started_at > estimated_preparation_time"]
        )
        
        for order in overdue_orders:
            # Solo notificar si no se ha notificado recientemente
            last_notification = order.notifications.filter(
                notification_type='delay'
            ).order_by('-created_at').first()
            
            if not last_notification or (
                timezone.now() - last_notification.created_at > timedelta(minutes=10)
            ):
                send_order_delay_notification(order)
                
                # Crear registro de notificación
                from app.orders.models import OrderNotification
                OrderNotification.objects.create(
                    order=order,
                    message=f"Orden {order.order_number} está retrasada",
                    notification_type='delay',
                    target_roles=['manager', 'waiter'],
                    is_sent=True,
                    sent_at=timezone.now()
                )
        
        if overdue_orders.exists():
            logger.warning(f"Se encontraron {overdue_orders.count()} órdenes atrasadas")
        
        return overdue_orders.count()
        
    except Exception as e:
        logger.error(f"Error verificando órdenes atrasadas: {str(e)}", exc_info=True)
        return 0


def cleanup_old_notifications():
    """
    Limpia notificaciones antiguas (más de 7 días).
    """
    try:
        from app.orders.models import OrderNotification
        
        cutoff_date = timezone.now() - timedelta(days=7)
        
        deleted_count = OrderNotification.objects.filter(
            created_at__lt=cutoff_date
        ).count()
        
        OrderNotification.objects.filter(
            created_at__lt=cutoff_date
        ).delete()
        
        if deleted_count > 0:
            logger.info(f"Limpiadas {deleted_count} notificaciones antiguas")
        
        return deleted_count
        
    except Exception as e:
        logger.error(f"Error limpiando notificaciones: {str(e)}", exc_info=True)
        return 0


def generate_daily_stats():
    """
    Genera estadísticas diarias de órdenes para cada negocio.
    """
    try:
        from app.business.models.business import Business
        from django.db.models import Count, Sum, Avg
        
        today = timezone.now().date()
        stats_generated = 0
        
        for business in Business.objects.filter(is_active=True):
            # Configurar contexto del esquema
            from app.business.services.business_service import DatabaseService
            DatabaseService.switch_to_business_schema(business.id)
            
            # Obtener estadísticas del día
            orders_today = Order.objects.filter(
                business=business,
                created_at__date=today
            )
            
            if orders_today.exists():
                stats = {
                    'business_id': business.id,
                    'date': today,
                    'total_orders': orders_today.count(),
                    'completed_orders': orders_today.filter(status=OrderStatus.DELIVERED).count(),
                    'cancelled_orders': orders_today.filter(status=OrderStatus.CANCELLED).count(),
                    'total_revenue': orders_today.filter(
                        status=OrderStatus.DELIVERED
                    ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
                    'avg_preparation_time': None
                }
                
                # Calcular tiempo promedio de preparación
                completed_orders = orders_today.filter(
                    status=OrderStatus.DELIVERED,
                    started_at__isnull=False,
                    delivered_at__isnull=False
                )
                
                if completed_orders.exists():
                    avg_seconds = completed_orders.extra(
                        select={'prep_time': 'EXTRACT(EPOCH FROM (delivered_at - started_at))'}
                    ).aggregate(Avg('prep_time'))['prep_time__avg']
                    
                    if avg_seconds:
                        stats['avg_preparation_time'] = timedelta(seconds=avg_seconds)
                
                # Aquí podrías guardar las estadísticas en una tabla de estadísticas
                # o enviarlas a un sistema de métricas externo
                
                logger.info(f"Estadísticas generadas para {business.name}: {stats}")
                stats_generated += 1
        
        return stats_generated
        
    except Exception as e:
        logger.error(f"Error generando estadísticas diarias: {str(e)}", exc_info=True)
        return 0


def auto_cancel_old_pending_orders():
    """
    Cancela automáticamente órdenes pendientes que tienen más de 30 minutos.
    """
    try:
        cutoff_time = timezone.now() - timedelta(minutes=30)
        
        old_pending_orders = Order.objects.filter(
            status=OrderStatus.PENDING,
            created_at__lt=cutoff_time
        )
        
        cancelled_count = 0
        
        for order in old_pending_orders:
            try:
                order.transition_to(
                    OrderStatus.CANCELLED,
                    notes="Cancelada automáticamente por inactividad"
                )
                cancelled_count += 1
                
                # Notificar cancelación automática
                from app.orders.models import OrderNotification
                OrderNotification.objects.create(
                    order=order,
                    message=f"Orden {order.order_number} cancelada automáticamente por inactividad",
                    notification_type='status_change',
                    target_roles=['manager'],
                    is_sent=True,
                    sent_at=timezone.now()
                )
                
            except Exception as e:
                logger.error(f"Error cancelando orden {order.order_number}: {str(e)}")
        
        if cancelled_count > 0:
            logger.info(f"Canceladas automáticamente {cancelled_count} órdenes pendientes antiguas")
        
        return cancelled_count
        
    except Exception as e:
        logger.error(f"Error en cancelación automática: {str(e)}", exc_info=True)
        return 0


def send_daily_summary():
    """
    Envía un resumen diario de órdenes a los managers.
    """
    try:
        from app.business.models.business import Business
        from django.db.models import Count, Sum
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
        channel_layer = get_channel_layer()
        today = timezone.now().date()
        summaries_sent = 0
        
        for business in Business.objects.filter(is_active=True):
            # Configurar contexto del esquema
            from app.business.services.business_service import DatabaseService
            DatabaseService.switch_to_business_schema(business.id)
            
            # Obtener resumen del día
            orders_today = Order.objects.filter(
                business=business,
                created_at__date=today
            )
            
            if orders_today.exists():
                summary = {
                    'total_orders': orders_today.count(),
                    'completed': orders_today.filter(status=OrderStatus.DELIVERED).count(),
                    'cancelled': orders_today.filter(status=OrderStatus.CANCELLED).count(),
                    'revenue': float(orders_today.filter(
                        status=OrderStatus.DELIVERED
                    ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0)
                }
                
                # Enviar resumen a managers via WebSocket
                manager_group = f"orders_managers_{business.id}"
                
                async_to_sync(channel_layer.group_send)(
                    manager_group,
                    {
                        'type': 'order_notification',
                        'notification_type': 'daily_summary',
                        'message': f'Resumen del día: {summary["total_orders"]} órdenes, {summary["completed"]} completadas, ${summary["revenue"]:.2f} en ventas',
                        'summary_data': summary,
                        'urgent': False
                    }
                )
                
                summaries_sent += 1
        
        logger.info(f"Enviados {summaries_sent} resúmenes diarios")
        return summaries_sent
        
    except Exception as e:
        logger.error(f"Error enviando resúmenes diarios: {str(e)}", exc_info=True)
        return 0


# Comando de management para ejecutar todas las tareas
class Command(BaseCommand):
    help = 'Ejecuta tareas de mantenimiento del sistema de órdenes'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--task',
            type=str,
            choices=['overdue', 'cleanup', 'stats', 'cancel', 'summary', 'all'],
            default='all',
            help='Especifica qué tarea ejecutar'
        )
    
    def handle(self, *args, **options):
        task = options['task']
        
        self.stdout.write(f"Ejecutando tarea: {task}")
        
        if task == 'overdue' or task == 'all':
            count = check_overdue_orders()
            self.stdout.write(f"Órdenes atrasadas verificadas: {count}")
        
        if task == 'cleanup' or task == 'all':
            count = cleanup_old_notifications()
            self.stdout.write(f"Notificaciones limpiadas: {count}")
        
        if task == 'stats' or task == 'all':
            count = generate_daily_stats()
            self.stdout.write(f"Estadísticas generadas para {count} negocios")
        
        if task == 'cancel' or task == 'all':
            count = auto_cancel_old_pending_orders()
            self.stdout.write(f"Órdenes canceladas automáticamente: {count}")
        
        if task == 'summary' or task == 'all':
            count = send_daily_summary()
            self.stdout.write(f"Resúmenes diarios enviados: {count}")
        
        self.stdout.write(
            self.style.SUCCESS('Tareas de mantenimiento completadas exitosamente')
        )