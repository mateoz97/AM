from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from django.urls import path
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from .models import Business, CustomUser,BusinessRole, RolePermission

# Filtro personalizado para negocios por propietario
class BusinessOwnerFilter(admin.SimpleListFilter):
    title = _('Propietario')
    parameter_name = 'owner_type'

    def lookups(self, request, model_admin):
        return (
            ('has_owner', _('Con propietario')),
            ('no_owner', _('Sin propietario')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'has_owner':
            return queryset.exclude(owner__isnull=True)
        if self.value() == 'no_owner':
            return queryset.filter(owner__isnull=True)


# Inline para ver miembros de un negocio
class BusinessMemberInline(admin.TabularInline):
    model = CustomUser
    fk_name = 'business'
    fields = ('username', 'email', 'role', 'is_active')
    extra = 0
    verbose_name = _("Miembro")
    verbose_name_plural = _("Miembros")
    max_num = 15  # Limitar el número de filas mostradas
    can_delete = False  # Prevenir eliminación desde inline


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'is_active', 'created_at', 'updated_at', 'member_count')
    list_filter = ('is_active', 'created_at', BusinessOwnerFilter)
    search_fields = ('name', 'address', 'email')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [BusinessMemberInline]
    
    fieldsets = (
        (_('Información básica'), {
            'fields': ('name', 'owner', 'is_active')
        }),
        (_('Información de contacto'), {
            'fields': ('address', 'phone', 'email', 'website')
        }),
        (_('Detalles adicionales'), {
            'fields': ('description', 'logo')
        }),
        (_('Fechas'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    actions = ['activate_businesses', 'deactivate_businesses']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/generate-report/',
                self.admin_site.admin_view(self.generate_report_view),
                name='business-generate-report',
            ),
        ]
        return custom_urls + urls

    def generate_report_view(self, request, object_id, *args, **kwargs):
        business = get_object_or_404(Business, pk=object_id)
        
        # Ejemplo simple: retornar información básica del negocio
        # En una implementación real, podrías generar un PDF, Excel, etc.
        context = {
            'business': business,
            'members': business.members.all(),
            'generated_at': timezone.now(),
            'title': f'Reporte de {business.name}',
        }
        
        # Para este ejemplo, simplemente renderizamos una plantilla
        # Deberías crear esta plantilla en app/auth_app/templates/admin/auth_app/business/report.html
        return render(request, 'admin/auth_app/business/report.html', context)

    def activate_businesses(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, _('%(count)d negocios han sido activados.') % {'count': updated})
    activate_businesses.short_description = _('Activar negocios seleccionados')

    def deactivate_businesses(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, _('%(count)d negocios han sido desactivados.') % {'count': updated})
    deactivate_businesses.short_description = _('Desactivar negocios seleccionados')
    
    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = _('Miembros')


# Inline para ver negocios donde el usuario es propietario
class UserOwnedBusinessInline(admin.TabularInline):
    model = Business
    fk_name = 'owner'
    fields = ('name', 'is_active', 'created_at')
    readonly_fields = ('created_at',)
    extra = 0
    verbose_name = _("Negocio propiedad")
    verbose_name_plural = _("Negocios propiedad")
    max_num = 5
    can_delete = False


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_business', 'get_business_role', 'is_active', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'business', 'business_role', 'is_verified')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'id_number')
    readonly_fields = ('date_joined', 'last_login')
    inlines = [UserOwnedBusinessInline]
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Información personal'), {'fields': ('first_name', 'last_name', 'email', 'phone', 'address',
                                              'profile_picture', 'date_of_birth', 'nationality', 'id_number')}),
        (_('Permisos'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_verified')}),
        # Aquí también cambiamos para usar solo business_role
        (_('Negocio y rol'), {'fields': ('business', 'business_role')}),
        (_('Fechas importantes'), {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
        (_('Información personal'), {
            'fields': ('first_name', 'last_name', 'phone')
        }),
        (_('Permisos'), {
            'fields': ('is_staff', 'is_active')
        }),
    )
    
    actions = ['activate_users', 'deactivate_users', 'verify_users']

    def get_business(self, obj):
        return obj.business.name if obj.business else _('Sin negocio')
    get_business.short_description = _('Negocio')
    get_business.admin_order_field = 'business__name'  # Permitir ordenamiento
    
    def get_business_role(self, obj):
        return obj.business_role.name if obj.business_role else _('Sin rol')
    get_business_role.short_description = _('Rol')
    get_business_role.admin_order_field = 'business_role__name'


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