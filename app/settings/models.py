# app/settings/models.py
from django.db import models
from django.contrib.auth import get_user_model
from app.business.models.business import Business

User = get_user_model()


class UserSettings(models.Model):
    """
    Configuraciones personales del usuario
    """
    THEME_CHOICES = [
        ('light', 'Claro'),
        ('dark', 'Oscuro'),
        ('auto', 'Automático'),
    ]
    
    LANGUAGE_CHOICES = [
        ('es', 'Español'),
        ('en', 'English'),
    ]
    
    FONT_SIZE_CHOICES = [
        ('small', 'Pequeño'),
        ('medium', 'Mediano'),
        ('large', 'Grande'),
    ]
    
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='user_settings'
    )
    
    # Configuraciones de apariencia
    theme = models.CharField(
        max_length=20, 
        choices=THEME_CHOICES, 
        default='light',
        verbose_name='Tema'
    )
    language = models.CharField(
        max_length=10, 
        choices=LANGUAGE_CHOICES, 
        default='es',
        verbose_name='Idioma'
    )
    font_size = models.CharField(
        max_length=20,
        choices=FONT_SIZE_CHOICES,
        default='medium',
        verbose_name='Tamaño de fuente'
    )
    compact_mode = models.BooleanField(
        default=False,
        verbose_name='Modo compacto'
    )
    
    # Configuraciones de notificaciones
    notifications_enabled = models.BooleanField(
        default=True,
        verbose_name='Notificaciones habilitadas'
    )
    email_notifications = models.BooleanField(
        default=True,
        verbose_name='Notificaciones por email'
    )
    order_updates = models.BooleanField(
        default=True,
        verbose_name='Actualizaciones de pedidos'
    )
    inventory_alerts = models.BooleanField(
        default=True,
        verbose_name='Alertas de inventario'
    )
    system_notifications = models.BooleanField(
        default=True,
        verbose_name='Notificaciones del sistema'
    )
    
    # Configuraciones de privacidad
    profile_visible = models.BooleanField(
        default=True,
        verbose_name='Perfil visible'
    )
    show_activity = models.BooleanField(
        default=False,
        verbose_name='Mostrar actividad'
    )
    allow_messages = models.BooleanField(
        default=True,
        verbose_name='Permitir mensajes'
    )
    
    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Configuración de Usuario'
        verbose_name_plural = 'Configuraciones de Usuario'
        db_table = 'settings_user_settings'
    
    def __str__(self):
        return f"Configuraciones de {self.user.username}"


class BusinessSettings(models.Model):
    """
    Configuraciones del negocio
    """
    business = models.OneToOneField(
        Business, 
        on_delete=models.CASCADE, 
        related_name='business_settings'
    )
    
    # Configuraciones de seguridad
    auto_logout_time = models.IntegerField(
        default=30,
        help_text='Tiempo en minutos para cerrar sesión automáticamente',
        verbose_name='Tiempo de auto logout (minutos)'
    )
    session_timeout = models.IntegerField(
        default=60,
        help_text='Tiempo máximo de sesión en minutos',
        verbose_name='Timeout de sesión (minutos)'
    )
    require_two_factor = models.BooleanField(
        default=False,
        verbose_name='Requiere autenticación de dos factores'
    )
    
    # Configuraciones operativas
    allow_customer_registration = models.BooleanField(
        default=True,
        verbose_name='Permitir registro de clientes'
    )
    require_order_confirmation = models.BooleanField(
        default=True,
        verbose_name='Requerir confirmación de pedidos'
    )
    enable_table_service = models.BooleanField(
        default=True,
        verbose_name='Habilitar servicio de mesa'
    )
    enable_takeaway = models.BooleanField(
        default=True,
        verbose_name='Habilitar para llevar'
    )
    enable_delivery = models.BooleanField(
        default=False,
        verbose_name='Habilitar delivery'
    )
    
    # Configuraciones de inventario
    low_stock_threshold = models.IntegerField(
        default=5,
        help_text='Cantidad mínima para alertas de stock bajo',
        verbose_name='Umbral de stock bajo'
    )
    auto_deduct_inventory = models.BooleanField(
        default=True,
        verbose_name='Deducir inventario automáticamente'
    )
    
    # Configuraciones de reportes
    daily_report_time = models.TimeField(
        null=True,
        blank=True,
        help_text='Hora para envío de reporte diario',
        verbose_name='Hora de reporte diario'
    )
    weekly_report_day = models.IntegerField(
        default=1,  # Lunes
        choices=[
            (1, 'Lunes'),
            (2, 'Martes'),
            (3, 'Miércoles'),
            (4, 'Jueves'),
            (5, 'Viernes'),
            (6, 'Sábado'),
            (7, 'Domingo'),
        ],
        verbose_name='Día de reporte semanal'
    )
    
    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Creado por'
    )
    
    class Meta:
        verbose_name = 'Configuración de Negocio'
        verbose_name_plural = 'Configuraciones de Negocio'
        db_table = 'settings_business_settings'
    
    def __str__(self):
        return f"Configuraciones de {self.business.name}"


class NotificationTemplate(models.Model):
    """
    Plantillas de notificaciones personalizables
    """
    NOTIFICATION_TYPES = [
        ('order_created', 'Pedido creado'),
        ('order_confirmed', 'Pedido confirmado'),
        ('order_ready', 'Pedido listo'),
        ('order_delivered', 'Pedido entregado'),
        ('low_stock', 'Stock bajo'),
        ('user_joined', 'Usuario se unió'),
        ('daily_report', 'Reporte diario'),
    ]
    
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='notification_templates'
    )
    notification_type = models.CharField(
        max_length=50,
        choices=NOTIFICATION_TYPES,
        verbose_name='Tipo de notificación'
    )
    title = models.CharField(
        max_length=200,
        verbose_name='Título'
    )
    message = models.TextField(
        verbose_name='Mensaje'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Activa'
    )
    
    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Plantilla de Notificación'
        verbose_name_plural = 'Plantillas de Notificación'
        unique_together = ['business', 'notification_type']
        db_table = 'settings_notification_template'
    
    def __str__(self):
        return f"{self.business.name} - {self.get_notification_type_display()}"