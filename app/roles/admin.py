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
    max_num = 1
    min_num = 1
    extra = 1
    
    def get_formset(self, request, obj=None, **kwargs):
        """Customize the formset to set default values based on role name"""
        formset = super().get_formset(request, obj, **kwargs)
        
        # If creating a new role, set default permissions based on role name
        if obj and hasattr(obj, 'get_default_permissions'):
            defaults = obj.get_default_permissions()
            for field_name, default_value in defaults.items():
                if field_name in formset.form.base_fields:
                    formset.form.base_fields[field_name].initial = default_value
        
        return formset

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
    
    def get_queryset(self, request):
        """Override to handle multitenant routing for business roles"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        # Filter by user's current business if not superuser
        if hasattr(request.user, 'current_business') and request.user.current_business:
            return qs.filter(business=request.user.current_business)
        return qs.none()
    
    def save_model(self, request, obj, form, change):
        """Ensure proper business context when saving"""
        # Always disable automatic permission creation in admin
        # Permissions will be handled by the inline form
        obj._admin_creation = True
        super().save_model(request, obj, form, change)
    
    def delete_model(self, request, obj):
        """Ensure proper business context when deleting"""
        super().delete_model(request, obj)

