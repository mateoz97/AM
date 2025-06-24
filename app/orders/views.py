# app/orders/views.py
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Sum, Avg
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
from decimal import Decimal
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging

from app.orders.models import Order, OrderItem, OrderStatus, OrderType, OrderPriority, OrderAuditLog
from app.orders.serializers import (
    OrderSerializer, OrderCreateSerializer, OrderSummarySerializer,
    OrderStatusUpdateSerializer, OrderAssignmentSerializer, 
    OrderHistorySerializer, OrderStatsSerializer, OrderCancellationSerializer,
    OrderItemManagementSerializer, OrderItemUpdateSerializer
)

logger = logging.getLogger(__name__)


class OrderViewSet(viewsets.ModelViewSet):
    """ViewSet principal para gestión de órdenes"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        """Retorna el serializer apropiado según la acción"""
        if self.action == 'create':
            return OrderCreateSerializer
        elif self.action == 'list':
            return OrderSummarySerializer
        elif self.action in ['update_status', 'change_status']:
            return OrderStatusUpdateSerializer
        elif self.action == 'assign_staff':
            return OrderAssignmentSerializer
        elif self.action == 'cancel_order':
            return OrderCancellationSerializer
        elif self.action == 'history':
            return OrderHistorySerializer
        elif self.action == 'stats':
            return OrderStatsSerializer
        return OrderSerializer
    
    def get_queryset(self):
        """Filtra órdenes según el contexto del negocio y permisos del usuario"""
        user = self.request.user
        business = user.current_business
        
        if not business:
            return Order.objects.none()
        
        # Configurar contexto del esquema
        from app.business.services.business_service import DatabaseService
        DatabaseService.switch_to_business_schema(business.id)
        
        # Filtrar según el rol del usuario
        queryset = Order.objects.filter(business=business)
        
        if user.current_business_role:
            role_name = user.current_business_role.name.lower()
            
            if role_name in ['admin', 'owner', 'manager']:
                # Managers ven todas las órdenes
                pass
            elif role_name in ['chef', 'cocinero', 'cook']:
                # Chefs ven órdenes en preparación y listas
                queryset = queryset.filter(
                    status__in=[OrderStatus.CONFIRMED, OrderStatus.PREPARING, OrderStatus.READY]
                )
            elif role_name in ['waiter', 'mesero', 'waitress']:
                # Meseros ven sus órdenes + no asignadas
                queryset = queryset.filter(
                    Q(waiter=user) | Q(waiter__isnull=True)
                )
        
        # Aplicar filtros de query parameters
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        priority_filter = self.request.query_params.get('priority')
        if priority_filter:
            queryset = queryset.filter(priority=priority_filter)
        
        date_filter = self.request.query_params.get('date')
        if date_filter:
            try:
                date_obj = datetime.strptime(date_filter, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__date=date_obj)
            except ValueError:
                pass
        
        return queryset.select_related(
            'customer', 'waiter', 'chef'
        ).prefetch_related('items').order_by('-created_at')
    
    def get_serializer_context(self):
        """Agrega contexto adicional al serializer"""
        context = super().get_serializer_context()
        if self.request.user.current_business:
            context['business'] = self.request.user.current_business
        return context
    
    def perform_create(self, serializer):
        """Crea una nueva orden y notifica en tiempo real"""
        business = self.request.user.current_business
        if not business:
            raise ValidationError("Debe tener un negocio activo para crear órdenes")
        
        # Configurar contexto del esquema
        from app.business.services.business_service import DatabaseService
        DatabaseService.switch_to_business_schema(business.id)
        
        # Crear la orden
        order = serializer.save(business=business)
        
        # Registrar auditoría
        order.log_audit(
            action='created',
            user=self.request.user,
            new_values={
                'order_number': order.order_number,
                'status': order.status,
                'total_amount': float(order.total_amount),
                'order_type': order.order_type
            },
            details=f"Orden creada con {order.items.count()} items",
            request=self.request
        )
        
        # Notificar en tiempo real
        self.broadcast_order_created(order)
        
        logger.info(f"Orden {order.order_number} creada por usuario {self.request.user.id}")
    
    def perform_update(self, serializer):
        """Actualiza una orden y notifica cambios"""
        old_instance = self.get_object()
        old_status = old_instance.status
        
        # Actualizar
        order = serializer.save()
        
        # Notificar cambios
        if order.status != old_status:
            self.broadcast_status_change(order, old_status, order.status)
        else:
            self.broadcast_order_updated(order)
        
        logger.info(f"Orden {order.order_number} actualizada por usuario {self.request.user.id}")
    
    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        """Actualiza solo el estado de una orden"""
        order = self.get_object()
        serializer = self.get_serializer(data=request.data, context={'order': order})
        
        if serializer.is_valid():
            old_status = order.status
            new_status = serializer.validated_data['status']
            notes = serializer.validated_data.get('notes', '')
            
            try:
                # Usar el método de transición segura
                order.transition_to(new_status, user=request.user, notes=notes)
                
                # Registrar auditoría
                order.log_audit(
                    action='status_changed',
                    user=request.user,
                    old_values={'status': old_status},
                    new_values={'status': new_status},
                    details=f"Estado cambiado de {old_status} a {new_status}. Notas: {notes}",
                    request=request
                )
                
                # Notificar cambio de estado
                self.broadcast_status_change(order, old_status, new_status)
                
                return Response({
                    'message': f'Estado cambiado a {order.get_status_display()}',
                    'order_id': str(order.id),
                    'old_status': old_status,
                    'new_status': new_status
                })
                
            except Exception as e:
                return Response({
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['patch'])
    def assign_staff(self, request, pk=None):
        """Asigna personal (mesero o chef) a una orden"""
        order = self.get_object()
        business = request.user.current_business
        
        # Verificar permisos
        if not self.can_assign_orders(request.user):
            return Response({
                'error': 'No tienes permisos para asignar órdenes'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = self.get_serializer(
            data=request.data, 
            context={'business': business}
        )
        
        if serializer.is_valid():
            assignment_type = serializer.validated_data['assignment_type']
            user_id = serializer.validated_data.get('user_id')
            
            try:
                if assignment_type == 'waiter':
                    if user_id:
                        from app.accounts.models.user import CustomUser
                        assigned_user = CustomUser.objects.get(id=user_id)
                        order.waiter = assigned_user
                    else:
                        order.waiter = None
                        
                elif assignment_type == 'chef':
                    if user_id:
                        from app.accounts.models.user import CustomUser
                        assigned_user = CustomUser.objects.get(id=user_id)
                        order.chef = assigned_user
                    else:
                        order.chef = None
                
                order.save()
                
                # Notificar asignación
                self.broadcast_order_assignment(order, assignment_type, user_id)
                
                assigned_name = "Sin asignar"
                if user_id:
                    assigned_name = assigned_user.get_full_name()
                
                return Response({
                    'message': f'{assignment_type.title()} asignado: {assigned_name}',
                    'order_id': str(order.id),
                    'assignment_type': assignment_type,
                    'assigned_user_id': user_id
                })
                
            except Exception as e:
                return Response({
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def cancel_order(self, request, pk=None):
        """Cancela una orden específica"""
        order = self.get_object()
        business = request.user.current_business
        
        # Verificar permisos para cancelar órdenes
        if not self.can_cancel_orders(request.user, order):
            return Response({
                'error': 'No tienes permisos para cancelar esta orden'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = self.get_serializer(
            data=request.data, 
            context={'order': order}
        )
        
        if serializer.is_valid():
            reason = serializer.validated_data.get('reason', '')
            refund_requested = serializer.validated_data.get('refund_requested', False)
            
            try:
                old_status = order.status
                
                # Crear notas de cancelación
                cancellation_notes = f"Orden cancelada por {request.user.get_full_name()}"
                if reason:
                    cancellation_notes += f". Motivo: {reason}"
                if refund_requested:
                    cancellation_notes += ". Reembolso solicitado."
                
                # Usar el método de transición segura
                order.transition_to(
                    OrderStatus.CANCELLED, 
                    user=request.user, 
                    notes=cancellation_notes
                )
                
                # Registrar auditoría
                order.log_audit(
                    action='cancelled',
                    user=request.user,
                    old_values={'status': old_status},
                    new_values={'status': OrderStatus.CANCELLED},
                    details=f"Orden cancelada. Motivo: {reason}. Reembolso solicitado: {refund_requested}",
                    request=request
                )
                
                # Notificar cancelación
                self.broadcast_order_cancellation(order, reason, refund_requested)
                
                logger.info(f"Orden {order.order_number} cancelada por usuario {request.user.id}")
                
                return Response({
                    'message': f'Orden {order.order_number} cancelada exitosamente',
                    'order_id': str(order.id),
                    'order_number': order.order_number,
                    'old_status': old_status,
                    'new_status': OrderStatus.CANCELLED,
                    'cancelled_at': order.cancelled_at,
                    'reason': reason,
                    'refund_requested': refund_requested
                })
                
            except Exception as e:
                return Response({
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def refund_order(self, request, pk=None):
        """Procesa un reembolso para una orden específica"""
        order = self.get_object()
        business = request.user.current_business
        
        # Verificar permisos para procesar reembolsos
        if not self.can_process_refunds(request.user):
            return Response({
                'error': 'No tienes permisos para procesar reembolsos'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Verificar que la orden esté en un estado que permita reembolso
        if order.status not in [OrderStatus.PAID, OrderStatus.DELIVERED, OrderStatus.CANCELLED]:
            return Response({
                'error': f'No se puede reembolsar una orden en estado {order.get_status_display()}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validar datos del reembolso
        refund_amount = request.data.get('refund_amount')
        refund_reason = request.data.get('refund_reason', '')
        partial_refund = request.data.get('partial_refund', False)
        
        # Si no se especifica monto, reembolsar el total
        if not refund_amount:
            refund_amount = order.total_amount
        else:
            try:
                refund_amount = Decimal(str(refund_amount))
            except (ValueError, TypeError):
                return Response({
                    'error': 'Monto de reembolso inválido'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validar que el monto no exceda el total de la orden
        if refund_amount > order.total_amount:
            return Response({
                'error': 'El monto de reembolso no puede exceder el total de la orden'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validar que no se haya reembolsado previamente
        if order.status == OrderStatus.REFUNDED:
            return Response({
                'error': 'Esta orden ya ha sido reembolsada'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            old_status = order.status
            
            # Crear notas del reembolso
            refund_notes = f"Reembolso procesado por {request.user.get_full_name()}"
            if refund_reason:
                refund_notes += f". Motivo: {refund_reason}"
            refund_notes += f". Monto: ${refund_amount}"
            if partial_refund:
                refund_notes += " (Reembolso parcial)"
            
            # Cambiar estado a reembolsada
            order.transition_to(
                OrderStatus.REFUNDED, 
                user=request.user, 
                notes=refund_notes
            )
            
            # Aquí se implementaría la lógica real de reembolso con el procesador de pagos
            # Por ahora simulamos un reembolso exitoso
            refund_success = True
            transaction_id = f"REF-{timezone.now().strftime('%Y%m%d')}-{order.order_number}"
            
            if refund_success:
                # Registrar auditoría
                order.log_audit(
                    action='refunded',
                    user=request.user,
                    old_values={'status': old_status},
                    new_values={'status': OrderStatus.REFUNDED},
                    details=f"Reembolso procesado. Monto: ${refund_amount}. Motivo: {refund_reason}. Transaction ID: {transaction_id}",
                    request=request
                )
                
                # Notificar reembolso
                self.broadcast_order_refund(order, refund_amount, refund_reason, transaction_id)
                
                logger.info(f"Reembolso procesado para orden {order.order_number} por usuario {request.user.id}")
                
                return Response({
                    'message': f'Reembolso procesado exitosamente para la orden {order.order_number}',
                    'order_id': str(order.id),
                    'order_number': order.order_number,
                    'old_status': old_status,
                    'new_status': OrderStatus.REFUNDED,
                    'refund_amount': refund_amount,
                    'transaction_id': transaction_id,
                    'refunded_at': order.updated_at,
                    'reason': refund_reason,
                    'partial_refund': partial_refund
                })
            else:
                # Si falla el reembolso, revertir el cambio de estado
                order.status = old_status
                order.save()
                
                return Response({
                    'error': 'Error al procesar el reembolso. Intente nuevamente.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def add_item(self, request, pk=None):
        """Agrega un nuevo item a la orden"""
        order = self.get_object()
        
        # Verificar permisos para modificar órdenes
        if not self.can_modify_orders(request.user, order):
            return Response({
                'error': 'No tienes permisos para modificar esta orden'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = OrderItemManagementSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                # Crear el nuevo item
                item_data = serializer.validated_data
                item_data['total_price'] = item_data['quantity'] * item_data['unit_price']
                
                new_item = OrderItem.objects.create(order=order, **item_data)
                
                # Actualizar totales de la orden
                order.refresh_from_db()
                order.save()  # Esto recalculará los totales
                
                # Serializar el item creado
                item_serializer = OrderItemSerializer(new_item)
                
                logger.info(f"Item agregado a orden {order.order_number} por usuario {request.user.id}")
                
                return Response({
                    'message': f'Item agregado exitosamente a la orden {order.order_number}',
                    'item': item_serializer.data,
                    'order_total': order.total_amount
                }, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                return Response({
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['patch'], url_path='items/(?P<item_id>[^/.]+)')
    def update_item(self, request, pk=None, item_id=None):
        """Actualiza un item específico de la orden"""
        order = self.get_object()
        
        # Verificar permisos para modificar órdenes
        if not self.can_modify_orders(request.user, order):
            return Response({
                'error': 'No tienes permisos para modificar esta orden'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            item = OrderItem.objects.get(id=item_id, order=order)
        except OrderItem.DoesNotExist:
            return Response({
                'error': 'Item no encontrado'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = OrderItemUpdateSerializer(item, data=request.data, partial=True)
        
        if serializer.is_valid():
            try:
                # Actualizar el item
                updated_item = serializer.save()
                
                # Recalcular el total_price si se cambió quantity o unit_price
                if 'quantity' in request.data or 'unit_price' in request.data:
                    updated_item.total_price = updated_item.quantity * updated_item.unit_price
                    updated_item.save()
                
                # Actualizar totales de la orden
                order.refresh_from_db()
                order.save()
                
                item_serializer = OrderItemSerializer(updated_item)
                
                logger.info(f"Item {item_id} actualizado en orden {order.order_number} por usuario {request.user.id}")
                
                return Response({
                    'message': f'Item actualizado exitosamente',
                    'item': item_serializer.data,
                    'order_total': order.total_amount
                })
                
            except Exception as e:
                return Response({
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['delete'], url_path='items/(?P<item_id>[^/.]+)')
    def remove_item(self, request, pk=None, item_id=None):
        """Elimina un item específico de la orden"""
        order = self.get_object()
        
        # Verificar permisos para modificar órdenes
        if not self.can_modify_orders(request.user, order):
            return Response({
                'error': 'No tienes permisos para modificar esta orden'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            item = OrderItem.objects.get(id=item_id, order=order)
        except OrderItem.DoesNotExist:
            return Response({
                'error': 'Item no encontrado'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Verificar que no sea el último item
        if order.items.count() <= 1:
            return Response({
                'error': 'No se puede eliminar el último item de la orden'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            item_name = item.product_name
            item.delete()
            
            # Actualizar totales de la orden
            order.refresh_from_db()
            order.save()
            
            logger.info(f"Item {item_name} eliminado de orden {order.order_number} por usuario {request.user.id}")
            
            return Response({
                'message': f'Item "{item_name}" eliminado exitosamente',
                'order_total': order.total_amount
            })
            
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """Obtiene el historial de cambios de una orden"""
        order = self.get_object()
        history = order.status_history.all()
        serializer = self.get_serializer(history, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def audit_log(self, request, pk=None):
        """Obtiene el registro de auditoría de una orden"""
        order = self.get_object()
        
        # Verificar permisos para ver auditoría
        if not self.can_view_audit_logs(request.user):
            return Response({
                'error': 'No tienes permisos para ver registros de auditoría'
            }, status=status.HTTP_403_FORBIDDEN)
        
        audit_logs = order.audit_logs.all()
        
        # Serializar logs manualmente para incluir información útil
        logs_data = []
        for log in audit_logs:
            logs_data.append({
                'id': str(log.id),
                'action': log.action,
                'action_display': log.get_action_display(),
                'user': {
                    'id': log.user.id,
                    'username': log.user.username,
                    'full_name': log.user.get_full_name()
                } if log.user else None,
                'old_values': log.old_values,
                'new_values': log.new_values,
                'details': log.details,
                'timestamp': log.timestamp.isoformat(),
                'ip_address': log.ip_address,
                'user_agent': log.user_agent
            })
        
        return Response(logs_data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Obtiene estadísticas detalladas de órdenes del negocio"""
        business = request.user.current_business
        if not business:
            return Response({
                'error': 'Debe tener un negocio activo'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Configurar contexto del esquema
        from app.business.services.business_service import DatabaseService
        DatabaseService.switch_to_business_schema(business.id)
        
        # Filtros de fecha
        date_filter = request.query_params.get('date', timezone.now().date())
        period = request.query_params.get('period', 'day')  # day, week, month, year
        
        if isinstance(date_filter, str):
            try:
                date_filter = datetime.strptime(date_filter, '%Y-%m-%d').date()
            except ValueError:
                date_filter = timezone.now().date()
        
        # Calcular rangos de fechas según el período
        end_date = date_filter
        if period == 'week':
            start_date = end_date - timedelta(days=7)
        elif period == 'month':
            start_date = end_date.replace(day=1)
        elif period == 'year':
            start_date = end_date.replace(month=1, day=1)
        else:  # day
            start_date = end_date
        
        # Órdenes del período
        orders_period = Order.objects.filter(
            business=business,
            created_at__date__range=[start_date, end_date]
        )
        
        # Órdenes del día específico
        orders_today = orders_period.filter(created_at__date=date_filter)
        
        # Estadísticas básicas por estado
        basic_stats = {
            'total_orders': orders_today.count(),
            'pending_orders': orders_today.filter(status=OrderStatus.PENDING).count(),
            'confirmed_orders': orders_today.filter(status=OrderStatus.CONFIRMED).count(),
            'preparing_orders': orders_today.filter(status=OrderStatus.PREPARING).count(),
            'ready_orders': orders_today.filter(status=OrderStatus.READY).count(),
            'paid_orders': orders_today.filter(status=OrderStatus.PAID).count(),
            'delivered_orders': orders_today.filter(status=OrderStatus.DELIVERED).count(),
            'cancelled_orders': orders_today.filter(status=OrderStatus.CANCELLED).count(),
            'refunded_orders': orders_today.filter(status=OrderStatus.REFUNDED).count(),
        }
        
        # Métricas financieras
        completed_orders = orders_today.filter(
            status__in=[OrderStatus.PAID, OrderStatus.DELIVERED]
        )
        financial_stats = {
            'total_revenue': completed_orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
            'average_order_value': completed_orders.aggregate(Avg('total_amount'))['total_amount__avg'] or 0,
            'total_tax': completed_orders.aggregate(Sum('tax_amount'))['tax_amount__sum'] or 0,
            'total_discounts': completed_orders.aggregate(Sum('discount_amount'))['discount_amount__sum'] or 0,
            'delivery_fees': completed_orders.aggregate(Sum('delivery_fee'))['delivery_fee__sum'] or 0,
        }
        
        # Métricas de tiempo
        delivered_orders = orders_today.filter(
            status=OrderStatus.DELIVERED,
            started_at__isnull=False,
            delivered_at__isnull=False
        )
        
        time_stats = {
            'average_preparation_time': 0,
            'fastest_order': 0,
            'slowest_order': 0,
            'orders_per_hour': 0,
            'peak_hour': None,
        }
        
        if delivered_orders.exists():
            # Calcular tiempos de preparación
            prep_times = []
            for order in delivered_orders:
                if order.started_at and order.delivered_at:
                    prep_time = (order.delivered_at - order.started_at).total_seconds()
                    prep_times.append(prep_time)
            
            if prep_times:
                time_stats.update({
                    'average_preparation_time': sum(prep_times) / len(prep_times),
                    'fastest_order': min(prep_times),
                    'slowest_order': max(prep_times),
                })
        
        # Calcular órdenes por hora y hora pico
        if basic_stats['total_orders'] > 0:
            hours_elapsed = max(
                (timezone.now() - timezone.make_aware(
                    datetime.combine(date_filter, datetime.min.time())
                )).total_seconds() / 3600,
                1
            )
            time_stats['orders_per_hour'] = round(basic_stats['total_orders'] / hours_elapsed, 2)
            
            # Encontrar hora pico
            hourly_orders = {}
            for order in orders_today:
                hour = order.created_at.hour
                hourly_orders[hour] = hourly_orders.get(hour, 0) + 1
            
            if hourly_orders:
                peak_hour = max(hourly_orders, key=hourly_orders.get)
                time_stats['peak_hour'] = {
                    'hour': peak_hour,
                    'orders': hourly_orders[peak_hour]
                }
        
        # Análisis por tipo de orden
        order_type_stats = {}
        for order_type, display_name in OrderType.choices:
            type_orders = orders_today.filter(order_type=order_type)
            order_type_stats[order_type] = {
                'count': type_orders.count(),
                'revenue': type_orders.filter(
                    status__in=[OrderStatus.PAID, OrderStatus.DELIVERED]
                ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
            }
        
        # Análisis por prioridad
        priority_stats = {}
        for priority, display_name in OrderPriority.choices:
            priority_orders = orders_today.filter(priority=priority)
            priority_stats[priority] = {
                'count': priority_orders.count(),
                'average_prep_time': 0
            }
            
            # Calcular tiempo promedio para esta prioridad
            priority_delivered = priority_orders.filter(
                status=OrderStatus.DELIVERED,
                started_at__isnull=False,
                delivered_at__isnull=False
            )
            
            if priority_delivered.exists():
                times = []
                for order in priority_delivered:
                    if order.started_at and order.delivered_at:
                        prep_time = (order.delivered_at - order.started_at).total_seconds()
                        times.append(prep_time)
                
                if times:
                    priority_stats[priority]['average_prep_time'] = sum(times) / len(times)
        
        # Métricas de comparación (período anterior)
        previous_period = {
            'start_date': start_date - (end_date - start_date + timedelta(days=1)),
            'end_date': start_date - timedelta(days=1)
        }
        
        previous_orders = Order.objects.filter(
            business=business,
            created_at__date__range=[previous_period['start_date'], previous_period['end_date']]
        )
        
        comparison_stats = {
            'previous_total_orders': previous_orders.count(),
            'previous_revenue': previous_orders.filter(
                status__in=[OrderStatus.PAID, OrderStatus.DELIVERED]
            ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
            'orders_growth': 0,
            'revenue_growth': 0,
        }
        
        # Calcular crecimiento
        if comparison_stats['previous_total_orders'] > 0:
            comparison_stats['orders_growth'] = (
                (basic_stats['total_orders'] - comparison_stats['previous_total_orders']) / 
                comparison_stats['previous_total_orders']
            ) * 100
        
        if comparison_stats['previous_revenue'] > 0:
            comparison_stats['revenue_growth'] = (
                (financial_stats['total_revenue'] - comparison_stats['previous_revenue']) / 
                comparison_stats['previous_revenue']
            ) * 100
        
        # Combinar todas las estadísticas
        comprehensive_stats = {
            'period': period,
            'date': date_filter.isoformat(),
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            **basic_stats,
            'financial': financial_stats,
            'timing': time_stats,
            'order_types': order_type_stats,
            'priorities': priority_stats,
            'comparison': comparison_stats,
        }
        
        serializer = self.get_serializer(comprehensive_stats)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Obtiene órdenes activas (pendientes, confirmadas, preparando, listas)"""
        business = request.user.current_business
        if not business:
            return Response([])
        
        # Configurar contexto del esquema
        from app.business.services.business_service import DatabaseService
        DatabaseService.switch_to_business_schema(business.id)
        
        active_orders = Order.objects.filter(
            business=business,
            status__in=[
                OrderStatus.PENDING,
                OrderStatus.CONFIRMED,
                OrderStatus.PREPARING,
                OrderStatus.READY,
                OrderStatus.PAID
            ]
        ).select_related(
            'customer', 'waiter', 'chef'
        ).prefetch_related('items').order_by('-created_at')
        
        serializer = OrderSerializer(active_orders, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def kitchen_display(self, request):
        """Vista especial para pantalla de cocina"""
        business = request.user.current_business
        if not business:
            return Response([])
        
        # Configurar contexto del esquema
        from app.business.services.business_service import DatabaseService
        DatabaseService.switch_to_business_schema(business.id)
        
        kitchen_orders = Order.objects.filter(
            business=business,
            status__in=[OrderStatus.CONFIRMED, OrderStatus.PREPARING]
        ).select_related('waiter').prefetch_related('items').order_by(
            'priority', 'created_at'
        )
        
        # Serializar con información específica para cocina
        orders_data = []
        for order in kitchen_orders:
            orders_data.append({
                'id': str(order.id),
                'order_number': order.order_number,
                'status': order.status,
                'priority': order.priority,
                'table_number': order.table_number,
                'created_at': order.created_at,
                'started_at': order.started_at,
                'estimated_ready_time': order.estimated_ready_time,
                'is_overdue': order.is_overdue,
                'kitchen_notes': order.kitchen_notes,
                'items': [
                    {
                        'id': str(item.id),
                        'product_name': item.product_name,
                        'quantity': item.quantity,
                        'modifications': item.modifications,
                        'cooking_instructions': item.cooking_instructions,
                        'status': item.status
                    }
                    for item in order.items.all()
                ]
            })
        
        return Response(orders_data)
    
    # Métodos auxiliares
    def can_assign_orders(self, user):
        """Verifica si el usuario puede asignar órdenes"""
        if not user.current_business_role:
            return False
        
        role_name = user.current_business_role.name.lower()
        return role_name in ['admin', 'owner', 'manager']
    
    def can_cancel_orders(self, user, order):
        """Verifica si el usuario puede cancelar órdenes"""
        if not user.current_business_role:
            return False
        
        role_name = user.current_business_role.name.lower()
        
        # Los administradores pueden cancelar cualquier orden
        admin_roles = ['admin', 'owner', 'manager', 'restaurant admin', 'administrador', 'gerente']
        if any(admin_role in role_name for admin_role in admin_roles):
            return True
        
        # Los meseros pueden cancelar sus propias órdenes si están pendientes
        waiter_roles = ['waiter', 'mesero', 'waitress', 'camarero']
        if any(waiter_role in role_name for waiter_role in waiter_roles):
            return (order.waiter == user and 
                   order.status in [OrderStatus.PENDING, OrderStatus.CONFIRMED])
        
        # Los clientes pueden cancelar sus órdenes si están pendientes
        if order.customer == user and order.status == OrderStatus.PENDING:
            return True
        
        return False
    
    def can_modify_orders(self, user, order):
        """Verifica si el usuario puede modificar órdenes (agregar/quitar items)"""
        if not user.current_business_role:
            return False
        
        role_name = user.current_business_role.name.lower()
        
        # Los administradores pueden modificar cualquier orden
        admin_roles = ['admin', 'owner', 'manager', 'restaurant admin', 'administrador', 'gerente']
        if any(admin_role in role_name for admin_role in admin_roles):
            return True
        
        # Los meseros pueden modificar sus propias órdenes antes de que estén listas
        waiter_roles = ['waiter', 'mesero', 'waitress', 'camarero']
        if any(waiter_role in role_name for waiter_role in waiter_roles):
            return (order.waiter == user and 
                   order.status in [OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PREPARING])
        
        return False
    
    def can_process_refunds(self, user):
        """Verifica si el usuario puede procesar reembolsos"""
        if not user.current_business_role:
            return False
        
        role_name = user.current_business_role.name.lower()
        
        # Solo administradores y managers pueden procesar reembolsos
        admin_roles = ['admin', 'owner', 'manager', 'restaurant admin', 'administrador', 'gerente']
        return any(admin_role in role_name for admin_role in admin_roles)
    
    def can_view_audit_logs(self, user):
        """Verifica si el usuario puede ver registros de auditoría"""
        if not user.current_business_role:
            return False
        
        role_name = user.current_business_role.name.lower()
        
        # Solo administradores y managers pueden ver auditorías
        admin_roles = ['admin', 'owner', 'manager', 'restaurant admin', 'administrador', 'gerente']
        return any(admin_role in role_name for admin_role in admin_roles)
    
    def broadcast_order_created(self, order):
        """Notifica creación de orden via WebSocket"""
        try:
            channel_layer = get_channel_layer()
            business_id = order.business.id
            
            # Serializar orden para broadcast
            order_data = OrderSerializer(order).data
            
            # Enviar a todos los grupos del negocio
            groups = [
                f"orders_business_{business_id}",
                f"orders_managers_{business_id}",
                f"orders_kitchen_{business_id}",
                f"orders_waiters_{business_id}"
            ]
            
            for group in groups:
                async_to_sync(channel_layer.group_send)(
                    group,
                    {
                        'type': 'order_created',
                        'order_data': order_data
                    }
                )
        except Exception as e:
            # Log error but don't fail the request
            logger.warning(f"Failed to broadcast order_created: {str(e)}")
    
    def broadcast_order_updated(self, order):
        """Notifica actualización de orden via WebSocket"""
        try:
            channel_layer = get_channel_layer()
            business_id = order.business.id
            
            order_data = OrderSerializer(order).data
            
            groups = [
                f"orders_business_{business_id}",
                f"orders_managers_{business_id}",
                f"orders_kitchen_{business_id}",
                f"orders_waiters_{business_id}"
            ]
            
            for group in groups:
                async_to_sync(channel_layer.group_send)(
                    group,
                    {
                        'type': 'order_updated',
                        'order_data': order_data
                    }
                )
        except Exception as e:
            logger.warning(f"Failed to broadcast order_updated: {str(e)}")
    
    def broadcast_status_change(self, order, old_status, new_status):
        """Notifica cambio de estado via WebSocket"""
        try:
            channel_layer = get_channel_layer()
            business_id = order.business.id
            
            groups = [
                f"orders_business_{business_id}",
                f"orders_managers_{business_id}",
                f"orders_kitchen_{business_id}",
                f"orders_waiters_{business_id}"
            ]
            
            for group in groups:
                async_to_sync(channel_layer.group_send)(
                    group,
                    {
                        'type': 'order_status_changed',
                        'order_id': str(order.id),
                        'order_number': order.order_number,
                        'old_status': old_status,
                        'new_status': new_status,
                        'new_status_display': order.get_status_display(),
                        'changed_by': self.request.user.get_full_name(),
                        'timestamp': timezone.now().isoformat()
                    }
                )
        except Exception as e:
            logger.warning(f"Failed to broadcast status_change: {str(e)}")
    
    def broadcast_order_assignment(self, order, assignment_type, user_id):
        """Notifica asignación de personal via WebSocket"""
        try:
            channel_layer = get_channel_layer()
            business_id = order.business.id
            
            assigned_name = "Sin asignar"
            if user_id:
                from app.accounts.models.user import CustomUser
                try:
                    assigned_user = CustomUser.objects.get(id=user_id)
                    assigned_name = assigned_user.get_full_name()
                except CustomUser.DoesNotExist:
                    pass
            
            groups = [
                f"orders_business_{business_id}",
                f"orders_managers_{business_id}"
            ]
            
            for group in groups:
                async_to_sync(channel_layer.group_send)(
                    group,
                    {
                        'type': 'order_assigned',
                        'order_id': str(order.id),
                        'assignment_type': assignment_type,
                        'assigned_to': assigned_name,
                        'message': f'{assignment_type.title()} asignado: {assigned_name}'
                    }
                )
        except Exception as e:
            logger.warning(f"Failed to broadcast order_assignment: {str(e)}")
    
    def broadcast_order_cancellation(self, order, reason=None, refund_requested=False):
        """Notifica cancelación de orden via WebSocket"""
        try:
            channel_layer = get_channel_layer()
            business_id = order.business.id
            
            # Serializar orden para broadcast
            order_data = OrderSerializer(order).data
            
            groups = [
                f"orders_business_{business_id}",
                f"orders_managers_{business_id}",
                f"orders_kitchen_{business_id}",
                f"orders_waiters_{business_id}"
            ]
            
            cancellation_message = f"Orden {order.order_number} cancelada"
            if reason:
                cancellation_message += f" - {reason}"
            
            for group in groups:
                async_to_sync(channel_layer.group_send)(
                    group,
                    {
                        'type': 'order_cancelled',
                        'order_data': order_data,
                        'order_id': str(order.id),
                        'order_number': order.order_number,
                        'reason': reason or '',
                        'refund_requested': refund_requested,
                        'cancelled_at': order.cancelled_at.isoformat() if order.cancelled_at else None,
                        'cancelled_by': self.request.user.get_full_name(),
                        'message': cancellation_message,
                        'timestamp': timezone.now().isoformat()
                    }
                )
        except Exception as e:
            logger.warning(f"Failed to broadcast order_cancellation: {str(e)}")
    
    def broadcast_order_refund(self, order, refund_amount, reason, transaction_id):
        """Notifica reembolso de orden via WebSocket"""
        try:
            channel_layer = get_channel_layer()
            business_id = order.business.id
            
            # Serializar orden para broadcast
            order_data = OrderSerializer(order).data
            
            groups = [
                f"orders_business_{business_id}",
                f"orders_managers_{business_id}",
                f"orders_waiters_{business_id}"
            ]
            
            refund_message = f"Orden {order.order_number} reembolsada - ${refund_amount}"
            if reason:
                refund_message += f" - {reason}"
            
            for group in groups:
                async_to_sync(channel_layer.group_send)(
                    group,
                    {
                        'type': 'order_refunded',
                        'order_data': order_data,
                        'order_id': str(order.id),
                        'order_number': order.order_number,
                        'refund_amount': float(refund_amount),
                        'reason': reason or '',
                        'transaction_id': transaction_id,
                        'refunded_at': order.updated_at.isoformat() if order.updated_at else None,
                        'refunded_by': self.request.user.get_full_name(),
                        'message': refund_message,
                        'timestamp': timezone.now().isoformat()
                    }
                )
        except Exception as e:
            logger.warning(f"Failed to broadcast order_refund: {str(e)}")