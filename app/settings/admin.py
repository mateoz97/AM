# app/settings/admin.py
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from app.settings.models import UserSettings, BusinessSettings, NotificationTemplate


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'theme', 'language', 'notifications_enabled', 
        'profile_visible', 'created_at'
    )
    list_filter = (
        'theme', 'language', 'notifications_enabled', 
        'profile_visible', 'created_at'
    )
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (_('Usuario'), {
            'fields': ('user',)
        }),
        (_('Apariencia'), {
            'fields': ('theme', 'language', 'font_size', 'compact_mode')
        }),
        (_('Notificaciones'), {
            'fields': (
                'notifications_enabled', 'email_notifications', 
                'order_updates', 'inventory_alerts', 'system_notifications'
            )
        }),
        (_('Privacidad'), {
            'fields': ('profile_visible', 'show_activity', 'allow_messages')
        }),
        (_('Metadatos'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        # Si el usuario no es superuser, filtrar por su negocio
        if hasattr(request.user, 'business') and request.user.business:
            return qs.filter(user__business=request.user.business)
        return qs.none()


@admin.register(BusinessSettings)
class BusinessSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'business', 'auto_logout_time', 'require_two_factor', 
        'allow_customer_registration', 'created_at'
    )
    list_filter = (
        'require_two_factor', 'allow_customer_registration', 
        'enable_table_service', 'enable_delivery', 'created_at'
    )
    search_fields = ('business__name',)
    readonly_fields = ('created_at', 'updated_at', 'created_by')
    
    fieldsets = (
        (_('Negocio'), {
            'fields': ('business',)
        }),
        (_('Seguridad'), {
            'fields': (
                'auto_logout_time', 'session_timeout', 'require_two_factor'
            )
        }),
        (_('Configuraciones Operativas'), {
            'fields': (
                'allow_customer_registration', 'require_order_confirmation',
                'enable_table_service', 'enable_takeaway', 'enable_delivery'
            )
        }),
        (_('Inventario'), {
            'fields': ('low_stock_threshold', 'auto_deduct_inventory')
        }),
        (_('Reportes'), {
            'fields': ('daily_report_time', 'weekly_report_day')
        }),
        (_('Metadatos'), {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        if hasattr(request.user, 'business') and request.user.business:
            return qs.filter(business=request.user.business)
        return qs.none()
    
    def save_model(self, request, obj, form, change):
        if not change:  # Solo si es nuevo
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = (
        'business', 'notification_type', 'title', 'is_active', 'created_at'
    )
    list_filter = ('notification_type', 'is_active', 'created_at')
    search_fields = ('business__name', 'title', 'message')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (_('Información'), {
            'fields': ('business', 'notification_type', 'is_active')
        }),
        (_('Contenido'), {
            'fields': ('title', 'message')
        }),
        (_('Metadatos'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        if hasattr(request.user, 'business') and request.user.business:
            return qs.filter(business=request.user.business)
        return qs.none()