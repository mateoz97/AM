# Django
from django.db import models
from django.utils.translation import gettext_lazy as _

        
class BusinessRole(models.Model):
    """
    Modelo para roles específicos de cada negocio.
    Cada negocio puede tener múltiples roles con diferentes permisos.
    """
    business = models.ForeignKey(
        'business.Business', 
        on_delete=models.CASCADE, 
        related_name='business_roles',
        verbose_name=_("Negocio"),
        swappable=True
    )
    name = models.CharField(_("Nombre del rol"), max_length=100)
    description = models.TextField(_("Descripción"), blank=True, null=True)
    is_default = models.BooleanField(_("Es rol predeterminado"), default=False)
    can_modify = models.BooleanField(_("Se puede modificar"), default=True)
    created_at = models.DateTimeField(_("Fecha de creación"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Fecha de actualización"), auto_now=True)
    
    class Meta:
        verbose_name = _("Rol de negocio")
        verbose_name_plural = _("Roles de negocio")
        unique_together = ('business', 'name')
        ordering = ['business', 'name']
    
    def __str__(self):
        return f"{self.business.name} - {self.name}"
    
    def save(self, *args, **kwargs):
        """Sobrescrito para manejar roles predeterminados"""
        creating = self.pk is None
        
        # Si es un rol de administrador, asegurarse que no sea modificable
        if self.name.lower() == 'administrador' or self.name.lower() == 'admin':
            self.is_default = True
            self.can_modify = False
            
        super().save(*args, **kwargs)
        
        # Al crear el rol, crear también sus permisos predeterminados
        if creating:
            default_permissions = self.get_default_permissions()
            RolePermission.objects.create(business_role=self, **default_permissions)
    
    def get_default_permissions(self):
        """Define permisos predeterminados según el nombre del rol"""
        permissions = {
            # Por defecto, sin permisos
            'can_view_dashboard': False,
            'can_manage_users': False,
            'can_manage_roles': False,
            'can_view_orders': False,
            'can_create_orders': False,
            'can_update_orders': False,
            'can_delete_orders': False,
            'can_view_inventory': False,
            'can_manage_inventory': False,
            'can_view_reports': False,
            'can_export_data': False,
        }
        
        # Administrador tiene todos los permisos
        if self.name.lower() in ['administrador', 'admin']:
            return {k: True for k in permissions}
            
        # Visualizador tiene permisos de solo lectura
        if self.name.lower() in ['visualizador', 'viewer']:
            permissions.update({
                'can_view_dashboard': True,
                'can_view_orders': True,
                'can_view_inventory': True,
                'can_view_reports': True,
            })
            
        # Otros roles comunes pueden tener permisos específicos
        if self.name.lower() == 'mesero':
            permissions.update({
                'can_view_dashboard': True,
                'can_view_orders': True,
                'can_create_orders': True,
                'can_update_orders': True,
                'can_view_inventory': True,
            })
            
        if self.name.lower() == 'cocinero':
            permissions.update({
                'can_view_dashboard': True,
                'can_view_orders': True,
                'can_update_orders': True,
                'can_view_inventory': True,
            })
            
        return permissions


class RolePermission(models.Model):
    """
    Permisos específicos para cada rol de negocio.
    Define las acciones que pueden realizar los usuarios con este rol.
    """
    
    business_role = models.OneToOneField(
        'roles.BusinessRole', 
        on_delete=models.CASCADE, 
        related_name='role_permissions',
        verbose_name=_("Rol")
    )
    
    # Permisos de Dashboard
    can_view_dashboard = models.BooleanField(_("Puede ver dashboard"), default=False)
    
    # Permisos de Usuarios
    can_manage_users = models.BooleanField(_("Puede gestionar usuarios"), default=False)
    can_manage_roles = models.BooleanField(_("Puede gestionar roles"), default=False)
    
    # Permisos de Pedidos
    can_view_orders = models.BooleanField(_("Puede ver pedidos"), default=False)
    can_create_orders = models.BooleanField(_("Puede crear pedidos"), default=False)
    can_update_orders = models.BooleanField(_("Puede actualizar pedidos"), default=False)
    can_delete_orders = models.BooleanField(_("Puede eliminar pedidos"), default=False)
    
    # Permisos de Inventario
    can_view_inventory = models.BooleanField(_("Puede ver inventario"), default=False)
    can_manage_inventory = models.BooleanField(_("Puede gestionar inventario"), default=False)
    
    # Permisos de Reportes
    can_view_reports = models.BooleanField(_("Puede ver reportes"), default=False)
    can_export_data = models.BooleanField(_("Puede exportar datos"), default=False)
    
    # Fechas de auditoría
    created_at = models.DateTimeField(_("Fecha de creación"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Fecha de actualización"), auto_now=True)
    
    class Meta:
        verbose_name = _("Permiso de rol")
        verbose_name_plural = _("Permisos de roles")
    
    def __str__(self):
        return f"Permisos para {self.business_role.name}"
    