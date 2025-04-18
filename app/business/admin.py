# Django admin configuration for the accounts
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.urls import path
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from datetime import timedelta

# Models
from app.business.models.business import Business, BusinessJoinRequest, BusinessInvitation
from app.accounts.models.user import CustomUser
from app.roles.models.role import BusinessRole

# Register your models here.
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

# # Inline para ver miembros de un negocio
class BusinessMemberInline(admin.TabularInline):
    model = CustomUser
    fk_name = 'business'
    fields = ('username', 'email', 'business_role', 'is_active')
    extra = 0
    verbose_name = _("Miembro")
    verbose_name_plural = _("Miembros")
    max_num = 15  # Limitar el número de filas mostradas
    can_delete = False  # Prevenir eliminación desde inline

# Añadir a BusinessAdmin en accounts/admin.py
class PendingRequestsInline(admin.TabularInline):
    model = BusinessJoinRequest
    fk_name = 'business'
    fields = ('user', 'status', 'created_at')
    readonly_fields = ('user', 'created_at')
    extra = 0
    verbose_name = _("Solicitud pendiente")
    verbose_name_plural = _("Solicitudes pendientes")
    max_num = 10
    can_delete = False
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(status='pending')


class BusinessInvitationsInline(admin.TabularInline):
    model = BusinessInvitation
    fk_name = 'business'
    fields = ('token', 'role', 'expires_at', 'used', 'created_at')
    readonly_fields = ('token', 'created_at')
    extra = 0
    verbose_name = _("Invitación")
    verbose_name_plural = _("Invitaciones")
    max_num = 5
    can_delete = True

class BusinessCoOwnersInline(admin.TabularInline):
    model = Business.co_owners.through
    verbose_name = _("Co-propietario")
    verbose_name_plural = _("Co-propietarios")
    extra = 1

@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'is_active', 'created_at', 'updated_at', 'member_count')
    list_filter = ('is_active', 'created_at', BusinessOwnerFilter)
    search_fields = ('name', 'address', 'email')
    readonly_fields = ('created_at', 'updated_at')
    # Añadir el inline a la configuración de BusinessAdmin
    inlines = [BusinessMemberInline, PendingRequestsInline, BusinessInvitationsInline, BusinessCoOwnersInline]
    exclude = ('co_owners',)
    
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
        # Deberías crear esta plantilla en app/accounts/templates/admin/accounts/business/report.html
        return render(request, 'admin/accounts/business/report.html', context)

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
    
    def delete_model(self, request, obj):
        """Sobrescribe el método de eliminación para el admin"""
        print(f"Eliminando negocio {obj.name} desde el admin")
        # Este método llamará automáticamente al método delete() del modelo,
        # que a su vez activará la señal pre_delete
        obj.delete()

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



@admin.register(BusinessJoinRequest)
class BusinessJoinRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'business', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at', 'business')
    search_fields = ('user__username', 'user__email', 'business__name', 'message')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['approve_requests', 'reject_requests']
    
    fieldsets = (
        (_('Información de solicitud'), {
            'fields': ('user', 'business', 'status', 'message')  # Añadir 'message'
        }),
        (_('Fechas'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def approve_requests(self, request, queryset):
        from app.accounts.services import BusinessRoleService
        
        updated = 0
        for join_request in queryset.filter(status='pending'):
            # Buscar rol de visualizador para el negocio
            viewer_role = BusinessRole.objects.filter(
                business=join_request.business,
                name__in=['viewer', 'Visualizador']
            ).first()
            
            # Si no existe, crear roles predeterminados
            if not viewer_role:
                roles = BusinessRoleService.create_default_roles(join_request.business)
                viewer_role = roles.get('viewer')
                
            # Asignar usuario al negocio con rol de visualizador
            user = join_request.user
            user.business = join_request.business
            user.business_role = viewer_role
            user.save(update_fields=['business', 'business_role'])
            
            # Actualizar estado de la solicitud
            join_request.status = 'approved'
            join_request.save(update_fields=['status'])
            updated += 1
            
        self.message_user(request, _('%(count)d solicitudes han sido aprobadas.') % {'count': updated})
    approve_requests.short_description = _('Aprobar solicitudes seleccionadas')
    
    def reject_requests(self, request, queryset):
        updated = queryset.filter(status='pending').update(status='rejected')
        self.message_user(request, _('%(count)d solicitudes han sido rechazadas.') % {'count': updated})
    reject_requests.short_description = _('Rechazar solicitudes seleccionadas')

@admin.register(BusinessInvitation)
class BusinessInvitationAdmin(admin.ModelAdmin):
    list_display = ('business', 'created_by', 'token', 'expires_at', 'used', 'created_at')
    list_filter = ('business', 'used', 'created_at')
    search_fields = ('business__name', 'created_by__username', 'token')
    readonly_fields = ('token', 'created_at')
    
    fieldsets = (
        (_('Información de invitación'), {
            'fields': ('business', 'created_by', 'token', 'role')
        }),
        (_('Estado'), {
            'fields': ('expires_at', 'used')
        }),
        (_('Fechas'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def generate_new_token(self, request, queryset):
        """Acción para generar nuevos tokens para invitaciones seleccionadas"""
        import secrets
        
        updated = 0
        for invitation in queryset:
            invitation.token = secrets.token_urlsafe(32)
            invitation.expires_at = timezone.now() + timedelta(days=7)
            invitation.used = False
            invitation.save()
            updated += 1
            
        self.message_user(request, _('%(count)d invitaciones han sido renovadas.') % {'count': updated})
    generate_new_token.short_description = _('Generar nuevos tokens')
    
    actions = ['generate_new_token']
    