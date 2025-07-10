# app/orders/models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from decimal import Decimal
import uuid
from enum import Enum
from datetime import datetime, timedelta
from django.utils import timezone
from app.core.managers import BusinessSpecificManager
from .state_machine import OrderStateMachine, OrderState, OrderTransitionValidator
import structlog

logger = structlog.get_logger(__name__)


class OrderStatus(models.TextChoices):
    """Estados de las órdenes con flujo definido"""
    PENDING = 'pending', _('Pendiente')
    CONFIRMED = 'confirmed', _('Confirmada')
    PREPARING = 'preparing', _('Preparando')
    READY = 'ready', _('Lista')
    PAID = 'paid', _('Pagada')
    DELIVERED = 'delivered', _('Entregada')
    CANCELLED = 'cancelled', _('Cancelada')
    REFUNDED = 'refunded', _('Reembolsada')


class OrderPriority(models.TextChoices):
    """Prioridades de las órdenes"""
    LOW = 'low', _('Baja')
    NORMAL = 'normal', _('Normal')
    HIGH = 'high', _('Alta')
    URGENT = 'urgent', _('Urgente')


class OrderType(models.TextChoices):
    """Tipos de órdenes"""
    DINE_IN = 'dine_in', _('Para comer aquí')
    TAKEAWAY = 'takeaway', _('Para llevar')
    DELIVERY = 'delivery', _('Domicilio')


class Order(models.Model):
    """
    Modelo principal de órdenes.
    Cada orden pertenece a un negocio específico y vive en su esquema.
    """
    
    # Identificación
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(
        _("Número de orden"),
        max_length=20,
        unique=True,
        db_index=True
    )
    
    # Relaciones principales
    business = models.ForeignKey(
        'business.Business',
        on_delete=models.CASCADE,
        related_name='orders',
        verbose_name=_("Negocio")
    )
    customer = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customer_orders',
        verbose_name=_("Cliente")
    )
    
    # Estado y flujo
    status = models.CharField(
        _("Estado"),
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
        db_index=True
    )
    priority = models.CharField(
        _("Prioridad"),
        max_length=20,
        choices=OrderPriority.choices,
        default=OrderPriority.NORMAL
    )
    order_type = models.CharField(
        _("Tipo de orden"),
        max_length=20,
        choices=OrderType.choices,
        default=OrderType.DINE_IN
    )
    
    # Información del pedido
    table_number = models.CharField(
        _("Número de mesa"),
        max_length=10,
        null=True,
        blank=True
    )
    customer_name = models.CharField(
        _("Nombre del cliente"),
        max_length=100,
        null=True,
        blank=True
    )
    customer_phone = models.CharField(
        _("Teléfono del cliente"),
        max_length=20,
        null=True,
        blank=True
    )
    delivery_address = models.TextField(
        _("Dirección de entrega"),
        null=True,
        blank=True
    )
    
    # Montos
    subtotal = models.DecimalField(
        _("Subtotal"),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    tax_amount = models.DecimalField(
        _("Impuestos"),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    discount_amount = models.DecimalField(
        _("Descuento"),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    delivery_fee = models.DecimalField(
        _("Costo de domicilio"),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_amount = models.DecimalField(
        _("Total"),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Personal asignado
    waiter = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='waiter_orders',
        verbose_name=_("Mesero")
    )
    chef = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chef_orders',
        verbose_name=_("Cocinero")
    )
    
    # Tiempos
    estimated_preparation_time = models.DurationField(
        _("Tiempo estimado de preparación"),
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(_("Creado"), auto_now_add=True)
    confirmed_at = models.DateTimeField(_("Confirmado"), null=True, blank=True)
    started_at = models.DateTimeField(_("Iniciado"), null=True, blank=True)
    ready_at = models.DateTimeField(_("Listo"), null=True, blank=True)
    paid_at = models.DateTimeField(_("Pagado"), null=True, blank=True)
    delivered_at = models.DateTimeField(_("Entregado"), null=True, blank=True)
    cancelled_at = models.DateTimeField(_("Cancelado"), null=True, blank=True)
    
    # Notas y observaciones
    customer_notes = models.TextField(
        _("Notas del cliente"),
        blank=True
    )
    kitchen_notes = models.TextField(
        _("Notas de cocina"),
        blank=True
    )
    internal_notes = models.TextField(
        _("Notas internas"),
        blank=True
    )
    
    # Metadata
    updated_at = models.DateTimeField(_("Actualizado"), auto_now=True)
    
    # Manager para esquemas de negocio
    objects = BusinessSpecificManager()
    
    class Meta:
        verbose_name = _("Orden")
        verbose_name_plural = _("Órdenes")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['business', 'status']),
            models.Index(fields=['order_number']),
            models.Index(fields=['waiter', 'status']),
            models.Index(fields=['chef', 'status']),
        ]
    
    def __str__(self):
        return f"Orden {self.order_number} - {self.get_status_display()}"
    
    def save(self, *args, **kwargs):
        # Generar número de orden si no existe
        if not self.order_number:
            self.order_number = self.generate_order_number()
        
        # Calcular total automáticamente
        self.calculate_total()
        
        # Actualizar timestamps según el estado
        self.update_status_timestamps()
        
        super().save(*args, **kwargs)
    
    def generate_order_number(self):
        """Genera un número único de orden para el negocio"""
        today = timezone.now().date()
        prefix = f"{today.strftime('%y%m%d')}"
        
        # Contar órdenes del día
        daily_count = Order.objects.filter(
            business=self.business,
            created_at__date=today
        ).count() + 1
        
        return f"{prefix}{daily_count:04d}"
    
    def calculate_total(self):
        """Calcula el total de la orden"""
        self.total_amount = (
            self.subtotal + 
            self.tax_amount + 
            self.delivery_fee - 
            self.discount_amount
        )
    
    def update_status_timestamps(self):
        """Actualiza timestamps automáticamente según el estado"""
        now = timezone.now()
        
        if self.status == OrderStatus.CONFIRMED and not self.confirmed_at:
            self.confirmed_at = now
        elif self.status == OrderStatus.PREPARING and not self.started_at:
            self.started_at = now
        elif self.status == OrderStatus.READY and not self.ready_at:
            self.ready_at = now
        elif self.status == OrderStatus.PAID and not self.paid_at:
            self.paid_at = now
        elif self.status == OrderStatus.DELIVERED and not self.delivered_at:
            self.delivered_at = now
        elif self.status == OrderStatus.CANCELLED and not self.cancelled_at:
            self.cancelled_at = now
    
    def can_transition_to(self, new_status):
        """Valida si se puede cambiar al nuevo estado"""
        transitions = {
            OrderStatus.PENDING: [OrderStatus.CONFIRMED, OrderStatus.CANCELLED],
            OrderStatus.CONFIRMED: [OrderStatus.PREPARING, OrderStatus.CANCELLED],
            OrderStatus.PREPARING: [OrderStatus.READY, OrderStatus.CANCELLED],
            OrderStatus.READY: [OrderStatus.PAID, OrderStatus.DELIVERED, OrderStatus.CANCELLED],
            OrderStatus.PAID: [OrderStatus.DELIVERED, OrderStatus.REFUNDED],
            OrderStatus.DELIVERED: [OrderStatus.REFUNDED],
            OrderStatus.CANCELLED: [],
            OrderStatus.REFUNDED: [],
        }
        
        return new_status in transitions.get(self.status, [])
    
    def transition_to(self, new_status, user=None, notes=None):
        """Cambia el estado de la orden de forma segura"""
        if not self.can_transition_to(new_status):
            raise ValidationError(
                f"No se puede cambiar de '{self.get_status_display()}' a '{dict(OrderStatus.choices)[new_status]}'"
            )
        
        old_status = self.status
        self.status = new_status
        self.save()
        
        # Crear evento de cambio de estado
        OrderStatusHistory.objects.create(
            order=self,
            old_status=old_status,
            new_status=new_status,
            changed_by=user,
            notes=notes or ''
        )
        
        return True
    
    def change_status(self, new_status, user=None, notes=None, force=False):
        """
        Cambia el estado de la orden usando la State Machine.
        
        Args:
            new_status: Nuevo estado
            user: Usuario que realiza el cambio
            notes: Notas adicionales
            force: Forzar cambio (solo para managers)
            
        Returns:
            bool: True si el cambio fue exitoso
            
        Raises:
            ValidationError: Si la transición no es válida
        """
        from_state = OrderState(self.status)
        to_state = OrderState(new_status)
        
        # Inicializar State Machine
        state_machine = OrderStateMachine(self)
        
        try:
            # Validar transición si no es forzada
            if not force:
                state_machine.validate_transition(from_state, to_state, user)
                OrderTransitionValidator.validate_business_rules(self, from_state, to_state)
            
            # Verificar si requiere confirmación
            if state_machine.requires_confirmation(from_state, to_state):
                if not notes:
                    raise ValidationError(
                        f"La transición {from_state.value} -> {to_state.value} requiere notas de confirmación"
                    )
            
            # Realizar el cambio
            old_status = self.status
            self.status = new_status
            
            # Actualizar timestamps automáticamente
            self.update_status_timestamps()
            
            # Guardar cambios
            self.save()
            
            # Registrar en historial
            self.log_status_change(old_status, new_status, user, notes)
            
            # Log estructurado
            logger.info("order_status_changed",
                       order_id=str(self.id),
                       order_number=self.order_number,
                       from_status=old_status,
                       to_status=new_status,
                       user_id=user.id if user else None,
                       notes=notes or '')
            
            return True
            
        except ValidationError as e:
            logger.warning("order_status_change_denied",
                          order_id=str(self.id),
                          order_number=self.order_number,
                          from_status=from_state.value,
                          to_status=to_state.value,
                          user_id=user.id if user else None,
                          error=str(e))
            raise
        except Exception as e:
            logger.error("order_status_change_error",
                        order_id=str(self.id),
                        order_number=self.order_number,
                        from_status=from_state.value,
                        to_status=to_state.value,
                        user_id=user.id if user else None,
                        error=str(e))
            raise ValidationError(f"Error al cambiar estado: {str(e)}")
    
    def get_next_valid_states(self, user=None):
        """
        Obtiene los estados válidos siguientes para un usuario.
        
        Args:
            user: Usuario (opcional)
            
        Returns:
            List[str]: Lista de estados válidos
        """
        current_state = OrderState(self.status)
        state_machine = OrderStateMachine(self)
        
        valid_states = state_machine.get_next_states(current_state, user)
        return [state.value for state in valid_states]
    
    def can_transition_to(self, new_status, user=None):
        """
        Verifica si se puede transicionar a un nuevo estado.
        
        Args:
            new_status: Estado objetivo
            user: Usuario (opcional)
            
        Returns:
            bool: True si la transición es válida
        """
        try:
            from_state = OrderState(self.status)
            to_state = OrderState(new_status)
            
            state_machine = OrderStateMachine(self)
            return state_machine.can_transition(from_state, to_state, user)
        except Exception:
            return False
    
    def log_audit(self, action, user=None, old_values=None, new_values=None, details=None, request=None):
        """Registra una acción de auditoría para esta orden"""
        try:
            audit_data = {
                'order': self,
                'action': action,
                'user': user,
                'old_values': old_values,
                'new_values': new_values,
                'details': details or '',
            }
            
            # Obtener información de la request si está disponible
            if request:
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    audit_data['ip_address'] = x_forwarded_for.split(',')[0]
                else:
                    audit_data['ip_address'] = request.META.get('REMOTE_ADDR')
                
                audit_data['user_agent'] = request.META.get('HTTP_USER_AGENT', '')
            
            OrderAuditLog.objects.create(**audit_data)
            
        except Exception as e:
            # No fallar si hay error en auditoría
            logger.error("audit_log_error", order_id=str(self.id), error=str(e))
    
    @property
    def preparation_time_elapsed(self):
        """Tiempo transcurrido desde que comenzó la preparación"""
        if self.started_at:
            return timezone.now() - self.started_at
        return None
    
    @property
    def is_overdue(self):
        """Verifica si la orden está atrasada"""
        if (self.estimated_preparation_time and 
            self.started_at and 
            self.status in [OrderStatus.PREPARING]):
            
            elapsed = self.preparation_time_elapsed
            return elapsed > self.estimated_preparation_time
        return False
    
    @property
    def estimated_ready_time(self):
        """Hora estimada de finalización"""
        if self.started_at and self.estimated_preparation_time:
            return self.started_at + self.estimated_preparation_time
        elif self.confirmed_at and self.estimated_preparation_time:
            return self.confirmed_at + self.estimated_preparation_time
        return None


class OrderItem(models.Model):
    """Items individuales de una orden"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name=_("Orden")
    )
    
    # Información del producto
    product_name = models.CharField(_("Nombre del producto"), max_length=200)
    product_description = models.TextField(_("Descripción"), blank=True)
    quantity = models.PositiveIntegerField(_("Cantidad"), default=1)
    unit_price = models.DecimalField(
        _("Precio unitario"),
        max_digits=10,
        decimal_places=2
    )
    total_price = models.DecimalField(
        _("Precio total"),
        max_digits=10,
        decimal_places=2
    )
    
    # Personalización
    modifications = models.TextField(
        _("Modificaciones"),
        blank=True,
        help_text=_("Ej: Sin cebolla, extra queso")
    )
    cooking_instructions = models.TextField(
        _("Instrucciones de cocina"),
        blank=True
    )
    
    # Estado del item
    status = models.CharField(
        _("Estado del item"),
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING
    )
    
    # Tiempos específicos del item
    started_cooking_at = models.DateTimeField(
        _("Inicio de cocción"),
        null=True,
        blank=True
    )
    finished_cooking_at = models.DateTimeField(
        _("Fin de cocción"),
        null=True,
        blank=True
    )
    
    # Manager para esquemas de negocio
    objects = BusinessSpecificManager()
    
    class Meta:
        verbose_name = _("Item de orden")
        verbose_name_plural = _("Items de orden")
    
    def __str__(self):
        return f"{self.quantity}x {self.product_name}"
    
    def save(self, *args, **kwargs):
        # Calcular precio total
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)
        
        # Actualizar subtotal de la orden
        self.order.subtotal = sum(
            item.total_price for item in self.order.items.all()
        )
        self.order.save()


class OrderStatusHistory(models.Model):
    """Historial de cambios de estado de órdenes"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='status_history',
        verbose_name=_("Orden")
    )
    
    old_status = models.CharField(
        _("Estado anterior"),
        max_length=20,
        choices=OrderStatus.choices
    )
    new_status = models.CharField(
        _("Nuevo estado"),
        max_length=20,
        choices=OrderStatus.choices
    )
    
    changed_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Cambiado por")
    )
    
    notes = models.TextField(_("Notas"), blank=True)
    timestamp = models.DateTimeField(_("Fecha y hora"), auto_now_add=True)
    
    # Manager para esquemas de negocio
    objects = BusinessSpecificManager()
    
    class Meta:
        verbose_name = _("Historial de estado")
        verbose_name_plural = _("Historiales de estado")
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.order.order_number}: {self.old_status} → {self.new_status}"


class OrderNotification(models.Model):
    """Notificaciones en tiempo real para órdenes"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name=_("Orden")
    )
    
    message = models.TextField(_("Mensaje"))
    notification_type = models.CharField(
        _("Tipo"),
        max_length=50,
        choices=[
            ('status_change', _('Cambio de estado')),
            ('assignment', _('Asignación')),
            ('delay', _('Retraso')),
            ('ready', _('Listo')),
            ('urgent', _('Urgente')),
        ]
    )
    
    # Audiencia objetivo
    target_roles = models.JSONField(
        _("Roles objetivo"),
        default=list,
        help_text=_("Lista de roles que deben recibir esta notificación")
    )
    
    # Estado de la notificación
    is_read = models.BooleanField(_("Leída"), default=False)
    is_sent = models.BooleanField(_("Enviada"), default=False)
    
    created_at = models.DateTimeField(_("Creada"), auto_now_add=True)
    sent_at = models.DateTimeField(_("Enviada"), null=True, blank=True)
    
    # Manager para esquemas de negocio
    objects = BusinessSpecificManager()
    
    class Meta:
        verbose_name = _("Notificación")
        verbose_name_plural = _("Notificaciones")
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Notificación para {self.order.order_number}: {self.notification_type}"


class OrderAuditLog(models.Model):
    """Registro de auditoría para operaciones en órdenes"""
    
    ACTION_CHOICES = [
        ('created', _('Creada')),
        ('updated', _('Actualizada')),
        ('status_changed', _('Estado cambiado')),
        ('assigned', _('Asignada')),
        ('item_added', _('Item agregado')),
        ('item_updated', _('Item actualizado')),
        ('item_removed', _('Item eliminado')),
        ('cancelled', _('Cancelada')),
        ('refunded', _('Reembolsada')),
        ('note_added', _('Nota agregada')),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='audit_logs',
        verbose_name=_("Orden")
    )
    
    action = models.CharField(
        _("Acción"),
        max_length=20,
        choices=ACTION_CHOICES
    )
    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Usuario")
    )
    
    # Datos de la acción
    old_values = models.JSONField(
        _("Valores anteriores"),
        null=True,
        blank=True,
        help_text=_("Valores antes del cambio")
    )
    new_values = models.JSONField(
        _("Valores nuevos"),
        null=True,
        blank=True,
        help_text=_("Valores después del cambio")
    )
    details = models.TextField(
        _("Detalles"),
        blank=True,
        help_text=_("Información adicional sobre la acción")
    )
    
    # Metadatos
    timestamp = models.DateTimeField(_("Fecha y hora"), auto_now_add=True)
    ip_address = models.GenericIPAddressField(
        _("Dirección IP"),
        null=True,
        blank=True
    )
    user_agent = models.TextField(
        _("User Agent"),
        blank=True
    )
    
    # Manager para esquemas de negocio
    objects = BusinessSpecificManager()
    
    class Meta:
        verbose_name = _("Registro de Auditoría")
        verbose_name_plural = _("Registros de Auditoría")
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['order', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
            models.Index(fields=['user', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.order.order_number}: {self.get_action_display()} por {self.user.username if self.user else 'Sistema'}"