# Django admin configuration for the accounts
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

# Models
from app.roles.models.role import BusinessRole
from app.roles.models.role import RolePermission


class RolePermissionInline(admin.StackedInline):
    model = RolePermission
    can_delete = False
    verbose_name = _("Permisos")
    verbose_name_plural = _("Permisos")

@admin.register(BusinessRole)
class BusinessRoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'is_default', 'can_modify', 'created_at')
    list_filter = ('business', 'is_default', 'can_modify')
    search_fields = ('name', 'business__name')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [RolePermissionInline]
    
    fieldsets = (
        (_('Información básica'), {
            'fields': ('business', 'name', 'description')
        }),
        (_('Configuración'), {
            'fields': ('is_default', 'can_modify')
        }),
        (_('Fechas'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

