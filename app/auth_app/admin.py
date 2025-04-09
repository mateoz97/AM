from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import Business, CustomUser

@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'address', 'email')
    readonly_fields = ('created_at', 'updated_at')
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

    def activate_businesses(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, _('%(count)d negocios han sido activados.') % {'count': updated})
    activate_businesses.short_description = _('Activar negocios seleccionados')

    def deactivate_businesses(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, _('%(count)d negocios han sido desactivados.') % {'count': updated})
    deactivate_businesses.short_description = _('Desactivar negocios seleccionados')


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_business', 'get_role', 'is_active', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'business', 'role')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'id_number')
    readonly_fields = ('date_joined', 'last_login')
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Información personal'), {'fields': ('first_name', 'last_name', 'email', 'phone', 'address',
                                              'profile_picture', 'date_of_birth', 'nationality', 'id_number')}),
        (_('Permisos'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_verified')}),
        (_('Negocio y rol'), {'fields': ('business', 'role')}),
        (_('Fechas importantes'), {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'is_staff', 'is_active'),
        }),
    )
    
    actions = ['activate_users', 'deactivate_users']

    def get_business(self, obj):
        return obj.business.name if obj.business else _('Sin negocio')
    get_business.short_description = _('Negocio')
    
    def get_role(self, obj):
        return obj.role.name if obj.role else _('Sin rol')
    get_role.short_description = _('Rol')

    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, _('%(count)d usuarios han sido activados.') % {'count': updated})
    activate_users.short_description = _('Activar usuarios seleccionados')

    def deactivate_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, _('%(count)d usuarios han sido desactivados.') % {'count': updated})
    deactivate_users.short_description = _('Desactivar usuarios seleccionados')