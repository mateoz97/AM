# app/orders/views.py
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Sum, Avg
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging

from app.orders.models import Order, OrderStatus
from app.orders.serializers import (
    OrderSerializer, OrderCreateSerializer, OrderSummarySerializer,
    OrderStatusUpdateSerializer, OrderAssignmentSerializer, 
    OrderHistorySerializer, OrderStatsSerializer
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
    
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """Obtiene el historial de cambios de una orden"""
        order = self.get_object()
        history = order.status_history.all()
        serializer = self.get_serializer(history, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Obtiene estadísticas de órdenes del negocio"""
        business = request.user.current_business
        if not business:
            return Response({
                'error': 'Debe tener un negocio activo'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Configurar contexto del esquema
        from app.business.services.business_service import DatabaseService
        DatabaseService.switch_to_business_schema(business.id)
        
        # Filtro de fecha (por defecto hoy)
        date_filter = request.query_params.get('date', timezone.now().date())
        if isinstance(date_filter, str):
            try:
                date_filter = datetime.strptime(date_filter, '%Y-%m-%d').date()
            except ValueError:
                date_filter = timezone.now().date()
        
        orders_today = Order.objects.filter(
            business=business,
            created_at__date=date_filter
        )
        
        stats = {
            'total_orders': orders_today.count(),
            'pending_orders': orders_today.filter(status=OrderStatus.PENDING).count(),
            'preparing_orders': orders_today.filter(status=OrderStatus.PREPARING).count(),
            'ready_orders': orders_today.filter(status=OrderStatus.READY).count(),
            'delivered_orders': orders_today.filter(status=OrderStatus.DELIVERED).count(),
            'cancelled_orders': orders_today.filter(status=OrderStatus.CANCELLED).count(),
            'total_revenue': orders_today.filter(
                status=OrderStatus.DELIVERED
            ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
            'average_preparation_time': timedelta(minutes=0),
            'orders_per_hour': 0
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
                stats['average_preparation_time'] = timedelta(seconds=avg_seconds)
        
        # Calcular órdenes por hora
        if stats['total_orders'] > 0:
            hours_elapsed = max(
                (timezone.now() - timezone.make_aware(
                    datetime.combine(date_filter, datetime.min.time())
                )).total_seconds() / 3600,
                1  # Al menos 1 hora para evitar división por cero
            )
            stats['orders_per_hour'] = round(stats['total_orders'] / hours_elapsed, 2)
        
        serializer = self.get_serializer(stats)
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
                OrderStatus.READY
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
    
    def broadcast_order_created(self, order):
        """Notifica creación de orden via WebSocket"""
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
    
    def broadcast_order_updated(self, order):
        """Notifica actualización de orden via WebSocket"""
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
    
    def broadcast_status_change(self, order, old_status, new_status):
        """Notifica cambio de estado via WebSocket"""
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
    
    def broadcast_order_assignment(self, order, assignment_type, user_id):
        """Notifica asignación de personal via WebSocket"""
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