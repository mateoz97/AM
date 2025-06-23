# app/orders/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from app.orders.models import Order, OrderItem, OrderStatusHistory, OrderNotification


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('total_price',)
    fields = ('product_name', 'quantity', 'unit_price', 'total_price', 'modifications', 'status')


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ('timestamp',)
    fields = ('old_status', 'new_status', 'changed_by', 'notes', 'timestamp')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number', 'business', 'status_badge', 'priority_badge', 
        'customer_name', 'total_amount', 'waiter', 'chef', 'created_at'
    )
    list_filter = ('status', 'priority', 'order_type', 'business', 'created_at')
    search_fields = ('order_number', 'customer_name', 'customer_phone', 'table_number')
    readonly_fields = (
        'id', 'order_number', 'total_amount', 'created_at', 'updated_at',
        'confirmed_at', 'started_at', 'ready_at', 'delivered_at', 'cancelled_at'
    )
    inlines = [OrderItemInline, OrderStatusHistoryInline]
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('id', 'order_number', 'business', 'status', 'priority', 'order_type')
        }),
        ('Cliente', {
            'fields': ('customer', 'customer_name', 'customer_phone', 'table_number', 'delivery_address')
        }),
        ('Montos', {
            'fields': ('subtotal', 'tax_amount', 'discount_amount', 'delivery_fee', 'total_amount')
        }),
        ('Asignaciones', {
            'fields': ('waiter', 'chef', 'estimated_preparation_time')
        }),
        ('Notas', {
            'fields': ('customer_notes', 'kitchen_notes', 'internal_notes'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'created_at', 'confirmed_at', 'started_at', 
                'ready_at', 'delivered_at', 'cancelled_at', 'updated_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        """Muestra el estado con color"""
        colors = {
            'pending': 'gray',
            'confirmed': 'blue',
            'preparing': 'orange',
            'ready': 'green',
            'delivered': 'darkgreen',
            'cancelled': 'red',
            'refunded': 'purple'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Estado'
    
    def priority_badge(self, obj):
        """Muestra la prioridad con color"""
        colors = {
            'low': 'green',
            'normal': 'blue',
            'high': 'orange',
            'urgent': 'red'
        }
        color = colors.get(obj.priority, 'blue')
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_priority_display()
        )
    priority_badge.short_description = 'Prioridad'
    
    actions = ['mark_as_confirmed', 'mark_as_preparing', 'mark_as_ready', 'mark_as_delivered']
    
    def mark_as_confirmed(self, request, queryset):
        """Marca órdenes como confirmadas"""
        updated = 0
        for order in queryset:
            if order.can_transition_to('confirmed'):
                order.transition_to('confirmed', user=request.user)
                updated += 1
        
        self.message_user(request, f'{updated} órdenes marcadas como confirmadas.')
    mark_as_confirmed.short_description = 'Marcar como confirmadas'
    
    def mark_as_preparing(self, request, queryset):
        """Marca órdenes como en preparación"""
        updated = 0
        for order in queryset:
            if order.can_transition_to('preparing'):
                order.transition_to('preparing', user=request.user)
                updated += 1
        
        self.message_user(request, f'{updated} órdenes marcadas como en preparación.')
    mark_as_preparing.short_description = 'Marcar como preparando'
    
    def mark_as_ready(self, request, queryset):
        """Marca órdenes como listas"""
        updated = 0
        for order in queryset:
            if order.can_transition_to('ready'):
                order.transition_to('ready', user=request.user)
                updated += 1
        
        self.message_user(request, f'{updated} órdenes marcadas como listas.')
    mark_as_ready.short_description = 'Marcar como listas'
    
    def mark_as_delivered(self, request, queryset):
        """Marca órdenes como entregadas"""
        updated = 0
        for order in queryset:
            if order.can_transition_to('delivered'):
                order.transition_to('delivered', user=request.user)
                updated += 1
        
        self.message_user(request, f'{updated} órdenes marcadas como entregadas.')
    mark_as_delivered.short_description = 'Marcar como entregadas'


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product_name', 'quantity', 'unit_price', 'total_price', 'status')
    list_filter = ('status', 'order__business')
    search_fields = ('product_name', 'order__order_number')
    readonly_fields = ('total_price',)


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('order', 'old_status', 'new_status', 'changed_by', 'timestamp')
    list_filter = ('old_status', 'new_status', 'timestamp')
    search_fields = ('order__order_number', 'notes')
    readonly_fields = ('timestamp',)


@admin.register(OrderNotification)
class OrderNotificationAdmin(admin.ModelAdmin):
    list_display = ('order', 'notification_type', 'message', 'is_sent', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_sent', 'is_read', 'created_at')
    search_fields = ('message', 'order__order_number')
    readonly_fields = ('created_at', 'sent_at')