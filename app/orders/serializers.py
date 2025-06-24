# app/orders/serializers.py
from rest_framework import serializers
from decimal import Decimal
from datetime import timedelta
from app.orders.models import Order, OrderItem, OrderStatus, OrderPriority, OrderType, OrderStatusHistory
from app.accounts.models.user import CustomUser


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer para items de órdenes"""
    
    class Meta:
        model = OrderItem
        fields = [
            'id', 'product_name', 'product_description', 'quantity',
            'unit_price', 'total_price', 'modifications', 'cooking_instructions',
            'status', 'started_cooking_at', 'finished_cooking_at'
        ]
        read_only_fields = ['id', 'started_cooking_at', 'finished_cooking_at']
    
    def validate_quantity(self, value):
        """Valida que la cantidad sea positiva"""
        if value <= 0:
            raise serializers.ValidationError("La cantidad debe ser mayor a cero")
        return value
    
    def validate_unit_price(self, value):
        """Valida que el precio sea positivo"""
        if value <= 0:
            raise serializers.ValidationError("El precio debe ser mayor a cero")
        return value
    
    def validate(self, attrs):
        """Calcula el total_price automáticamente"""
        quantity = attrs.get('quantity')
        unit_price = attrs.get('unit_price')
        
        if quantity and unit_price:
            attrs['total_price'] = quantity * unit_price
        
        return attrs


class UserBasicSerializer(serializers.ModelSerializer):
    """Serializer básico para usuarios en órdenes"""
    
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'full_name', 'first_name', 'last_name']
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    """Serializer principal para órdenes"""
    
    items = OrderItemSerializer(many=True, required=False)
    customer_detail = UserBasicSerializer(source='customer', read_only=True)
    waiter_detail = UserBasicSerializer(source='waiter', read_only=True)
    chef_detail = UserBasicSerializer(source='chef', read_only=True)
    
    # Hacer campos opcionales explícitamente
    customer_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    customer_phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    table_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    # Campos calculados
    preparation_time_elapsed = serializers.CharField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    estimated_ready_time = serializers.DateTimeField(read_only=True)
    
    # Campos de solo lectura para timestamps
    created_at = serializers.DateTimeField(read_only=True)
    confirmed_at = serializers.DateTimeField(read_only=True)
    started_at = serializers.DateTimeField(read_only=True)
    ready_at = serializers.DateTimeField(read_only=True)
    delivered_at = serializers.DateTimeField(read_only=True)
    cancelled_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'status', 'priority', 'order_type',
            'table_number', 'customer_name', 'customer_phone', 'delivery_address',
            'subtotal', 'tax_amount', 'discount_amount', 'delivery_fee', 'total_amount',
            'customer', 'customer_detail', 'waiter', 'waiter_detail', 
            'chef', 'chef_detail', 'estimated_preparation_time',
            'customer_notes', 'kitchen_notes', 'internal_notes',
            'created_at', 'confirmed_at', 'started_at', 'ready_at', 
            'delivered_at', 'cancelled_at', 'updated_at',
            'preparation_time_elapsed', 'is_overdue', 'estimated_ready_time',
            'items'
        ]
        read_only_fields = [
            'id', 'order_number', 'subtotal', 'total_amount',
            'created_at', 'confirmed_at', 'started_at', 'ready_at', 
            'delivered_at', 'cancelled_at', 'updated_at',
            'preparation_time_elapsed', 'is_overdue', 'estimated_ready_time'
        ]
    
    def validate_status(self, value):
        """Valida transiciones de estado"""
        if self.instance:  # Solo validar en actualizaciones
            if not self.instance.can_transition_to(value):
                current_status = self.instance.get_status_display()
                new_status = dict(OrderStatus.choices)[value]
                raise serializers.ValidationError(
                    f"No se puede cambiar de '{current_status}' a '{new_status}'"
                )
        return value
    
    def validate_estimated_preparation_time(self, value):
        """Valida que el tiempo de preparación sea razonable"""
        if value and value > timedelta(hours=8):
            raise serializers.ValidationError(
                "El tiempo de preparación no puede ser mayor a 8 horas"
            )
        return value
    
    def validate_order_type(self, value):
        """Valida campos requeridos según el tipo de orden"""
        if value == OrderType.DELIVERY and not self.initial_data.get('delivery_address'):
            raise serializers.ValidationError(
                "La dirección de entrega es requerida para órdenes de domicilio"
            )
        return value
    
    def validate(self, attrs):
        """Validaciones cruzadas"""
        # Validar que hay items si es una nueva orden
        if not self.instance and not attrs.get('items'):
            raise serializers.ValidationError(
                "Una orden debe tener al menos un item"
            )
        
        # Validar asignaciones según el estado
        status = attrs.get('status', self.instance.status if self.instance else OrderStatus.PENDING)
        
        if status == OrderStatus.PREPARING and not attrs.get('chef'):
            if not self.instance or not self.instance.chef:
                raise serializers.ValidationError(
                    "Se debe asignar un chef antes de comenzar la preparación"
                )
        
        return attrs
    
    def create(self, validated_data):
        """Crea una nueva orden con sus items"""
        items_data = validated_data.pop('items', [])
        
        # Crear la orden
        order = Order.objects.create(**validated_data)
        
        # Crear los items
        for item_data in items_data:
            OrderItem.objects.create(order=order, **item_data)
        
        return order
    
    def update(self, instance, validated_data):
        """Actualiza una orden existente"""
        items_data = validated_data.pop('items', None)
        
        # Actualizar campos de la orden
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Manejar cambio de estado
        old_status = instance.status
        new_status = validated_data.get('status')
        
        if new_status and old_status != new_status:
            # Usar el método de transición segura
            instance.transition_to(
                new_status, 
                user=self.context.get('user'),
                notes=validated_data.get('internal_notes', '')
            )
        else:
            instance.save()
        
        # Actualizar items si se proporcionaron
        if items_data is not None:
            # Eliminar items existentes
            instance.items.all().delete()
            
            # Crear nuevos items
            for item_data in items_data:
                OrderItem.objects.create(order=instance, **item_data)
        
        return instance


class OrderCreateSerializer(serializers.ModelSerializer):
    """Serializer optimizado para crear órdenes"""
    
    items = OrderItemSerializer(many=True)
    
    # Hacer campos opcionales explícitamente
    customer_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    customer_phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    table_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    class Meta:
        model = Order
        fields = [
            'order_type', 'table_number', 'customer_name', 'customer_phone',
            'delivery_address', 'customer', 'priority', 'tax_amount',
            'discount_amount', 'delivery_fee', 'estimated_preparation_time',
            'customer_notes', 'items'
        ]
    
    def validate_items(self, value):
        """Valida que hay al menos un item"""
        if not value:
            raise serializers.ValidationError("Debe agregar al menos un item a la orden")
        return value
    
    def create(self, validated_data):
        """Crea una orden optimizada para alta concurrencia"""
        items_data = validated_data.pop('items')
        
        # Agregar datos automáticos
        validated_data['business'] = self.context['business']
        
        # Crear orden
        order = Order.objects.create(**validated_data)
        
        # Crear items en batch
        items_to_create = [
            OrderItem(order=order, **item_data)
            for item_data in items_data
        ]
        OrderItem.objects.bulk_create(items_to_create)
        
        # Recalcular totales
        order.refresh_from_db()
        order.save()  # Esto triggereará el cálculo de totales
        
        return order


class OrderStatusUpdateSerializer(serializers.Serializer):
    """Serializer para actualizar solo el estado de una orden"""
    
    status = serializers.ChoiceField(choices=OrderStatus.choices)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=500)
    
    def validate_status(self, value):
        """Valida que la transición sea válida"""
        order = self.context['order']
        if not order.can_transition_to(value):
            current_status = order.get_status_display()
            new_status = dict(OrderStatus.choices)[value]
            raise serializers.ValidationError(
                f"No se puede cambiar de '{current_status}' a '{new_status}'"
            )
        return value


class OrderAssignmentSerializer(serializers.Serializer):
    """Serializer para asignar personal a órdenes"""
    
    assignment_type = serializers.ChoiceField(choices=['waiter', 'chef'])
    user_id = serializers.IntegerField(required=False, allow_null=True)
    
    def validate_user_id(self, value):
        """Valida que el usuario existe y tiene el rol apropiado"""
        if value is None:
            return None
        
        try:
            user = CustomUser.objects.get(id=value)
            business = self.context['business']
            
            # Verificar que el usuario pertenece al negocio
            if user.current_business != business:
                raise serializers.ValidationError(
                    "El usuario no pertenece a este negocio"
                )
            
            return value
            
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("Usuario no encontrado")


class OrderHistorySerializer(serializers.ModelSerializer):
    """Serializer para el historial de cambios de estado"""
    
    changed_by_detail = UserBasicSerializer(source='changed_by', read_only=True)
    old_status_display = serializers.CharField(source='get_old_status_display', read_only=True)
    new_status_display = serializers.CharField(source='get_new_status_display', read_only=True)
    
    class Meta:
        model = OrderStatusHistory
        fields = [
            'id', 'old_status', 'old_status_display', 'new_status', 'new_status_display',
            'changed_by', 'changed_by_detail', 'notes', 'timestamp'
        ]
        read_only_fields = fields


class OrderSummarySerializer(serializers.ModelSerializer):
    """Serializer resumido para listados de órdenes"""
    
    items_count = serializers.SerializerMethodField()
    waiter_name = serializers.CharField(source='waiter.get_full_name', read_only=True)
    chef_name = serializers.CharField(source='chef.get_full_name', read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'status', 'priority', 'order_type',
            'table_number', 'customer_name', 'total_amount',
            'created_at', 'estimated_ready_time', 'is_overdue',
            'waiter_name', 'chef_name', 'items_count'
        ]
        read_only_fields = fields
    
    def get_items_count(self, obj):
        """Cuenta el número de items en la orden"""
        return obj.items.count()


class OrderCancellationSerializer(serializers.Serializer):
    """Serializer para cancelar órdenes"""
    
    reason = serializers.CharField(
        required=False, 
        allow_blank=True, 
        max_length=500,
        help_text="Motivo de la cancelación"
    )
    refund_requested = serializers.BooleanField(
        default=False,
        help_text="Indica si se solicita reembolso"
    )
    
    def validate(self, attrs):
        """Valida que la orden pueda ser cancelada"""
        order = self.context['order']
        
        # Verificar que la orden se puede cancelar
        if not order.can_transition_to(OrderStatus.CANCELLED):
            current_status = order.get_status_display()
            raise serializers.ValidationError(
                f"No se puede cancelar una orden en estado '{current_status}'"
            )
        
        return attrs


class OrderStatsSerializer(serializers.Serializer):
    """Serializer para estadísticas de órdenes"""
    
    total_orders = serializers.IntegerField()
    pending_orders = serializers.IntegerField()
    preparing_orders = serializers.IntegerField()
    ready_orders = serializers.IntegerField()
    delivered_orders = serializers.IntegerField()
    cancelled_orders = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    average_preparation_time = serializers.DurationField()
    orders_per_hour = serializers.DecimalField(max_digits=5, decimal_places=2)