from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.utils.translation import gettext_lazy as _


class Business(models.Model):
    name = models.CharField(_("Nombre"), max_length=255, unique=True)
    owner = models.ForeignKey(
        "auth_app.CustomUser",
        on_delete=models.SET_NULL,
        related_name="owned_businesses",
        null=True,
        blank=True,
        verbose_name=_("Propietario")
    )
    created_at = models.DateTimeField(_("Fecha de creación"), auto_now_add=True)
    is_active = models.BooleanField(_("Activo"), default=True)
    updated_at = models.DateTimeField(_("Última actualización"), auto_now=True)
    description = models.TextField(_("Descripción"), null=True, blank=True)
    address = models.CharField(_("Dirección"), max_length=255, null=True, blank=True)
    phone = models.CharField(_("Teléfono"), max_length=20, null=True, blank=True)
    email = models.EmailField(_("Email de contacto"), null=True, blank=True)
    website = models.URLField(_("Sitio web"), null=True, blank=True)
    logo = models.ImageField(_("Logo"), upload_to="business_logos/", null=True, blank=True)

    class Meta:
        verbose_name = _("Negocio")
        verbose_name_plural = _("Negocios")
        ordering = ['-created_at']
        permissions = [
            ("view_inactive_business", _("Puede ver negocios inactivos")),
            ("activate_business", _("Puede activar o desactivar negocios")),
        ]

    def __str__(self):
        status = _("activo") if self.is_active else _("inactivo")
        return f"{self.name} ({status})"
    
    def get_active_members(self):
        """Retorna todos los miembros activos del negocio"""
        return self.members.filter(is_active=True)
    
    def save(self, *args, **kwargs):
        # Código existente para manejar el nombre
        if self.name:
            self.name = self.name.replace(" ", "_")
        
        # Detectar cambio de propietario
        owner_changed = False
        old_owner = None
        if not self.pk is None:
            try:
                old_instance = Business.objects.get(pk=self.pk)
                if old_instance.owner != self.owner:
                    owner_changed = True
                    old_owner = old_instance.owner
            except Business.DoesNotExist:
                pass
        
        # Guardar primero el negocio
        super().save(*args, **kwargs)
        
        # Si el propietario cambió, actualizar las relaciones
        if owner_changed and old_owner:
            # Si el antiguo propietario tenía este negocio como su negocio, eliminamos esa relación
            if old_owner.business == self:
                old_owner.business = None
                old_owner.save(update_fields=['business'])
        
        # Actualizar el nuevo propietario si existe
        if self.owner and (owner_changed or self.owner.business is None):
            # Sólo actualizamos si el propietario no tiene ya un negocio o si tenemos permiso para cambiarlo
            self.owner.business = self
            self.owner.save(update_fields=['business'])
        
        # Código existente para crear base de datos
        if self.pk is None and self.id:
            from .services import DatabaseService
            DatabaseService.create_business_database(self)

class CustomUser(AbstractUser):  
    business = models.ForeignKey(
        "auth_app.Business", 
        on_delete=models.SET_NULL, 
        related_name="members",
        null=True, 
        blank=True,
        verbose_name=_("Negocio")
    )
    role = models.ForeignKey(
        Group, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name=_("Rol")
    )
    
    business_role = models.ForeignKey(
        "auth_app.BusinessRole",
        on_delete=models.SET_NULL,
        related_name="users",
        null=True,
        blank=True,
        verbose_name=_("Rol de negocio")
    )

    groups = models.ManyToManyField(
        Group,
        related_name="auth_app_users", 
        blank=True,
        verbose_name=_("grupos")
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name="auth_app_users_permissions",
        blank=True,
        verbose_name=_("permisos de usuario")
    )
    
    id_number = models.CharField(_("Número de identificación"), max_length=20, unique=True, null=True, blank=True)
    username = models.CharField(_("Nombre de usuario"), max_length=150, unique=True)
    password = models.CharField(_("Contraseña"), max_length=128)
    first_name = models.CharField(_("Nombre"), max_length=30, blank=True)
    last_name = models.CharField(_("Apellido"), max_length=30, blank=True)
    email = models.EmailField(_("Correo electrónico"), unique=True)
    is_active = models.BooleanField(_("Activo"), default=True)
    is_staff = models.BooleanField(_("Es staff"), default=False)
    is_superuser = models.BooleanField(_("Es superusuario"), default=False)
    date_joined = models.DateTimeField(_("Fecha de registro"), auto_now_add=True)
    last_login = models.DateTimeField(_("Último ingreso"), null=True, blank=True)
    is_verified = models.BooleanField(_("Verificado"), default=False)
    phone = models.CharField(_("Teléfono"), max_length=20, null=True, blank=True)
    address = models.CharField(_("Dirección"), max_length=255, null=True, blank=True)
    profile_picture = models.ImageField(_("Foto de perfil"), upload_to="profile_pictures/", null=True, blank=True)
    date_of_birth = models.DateField(_("Fecha de nacimiento"), null=True, blank=True)
    nationality = models.CharField(_("Nacionalidad"), max_length=50, null=True, blank=True)
    
    class Meta:
        verbose_name = _("Usuario")
        verbose_name_plural = _("Usuarios")
        ordering = ['username']
        permissions = [
            ("change_user_role", _("Puede cambiar el rol de un usuario")),
            ("assign_to_business", _("Puede asignar usuarios a negocios")),
        ]

    def __str__(self):
        role_name = self.role.name if self.role else _('Sin rol')
        business_name = self.business.name if self.business else _('Sin negocio')
        return f"{self.get_full_name() or self.username} - {role_name} ({business_name})"
    
    def has_role(self, role_name):
        """Verifica si el usuario tiene un rol específico"""
        if not self.role:
            return False
        
        # Permite verificar tanto el nombre completo como solo la parte del rol
        business_prefix = f"{self.business.name}_" if self.business else ""
        full_role_name = f"{business_prefix}{role_name}"
        
        return (self.role.name == role_name or 
                self.role.name == full_role_name or 
                self.role.name.endswith(f"_{role_name}"))
    
    def get_full_name(self):
        """Retorna el nombre completo del usuario"""
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name if full_name else self.username
    
    def has_business_permission(self, permission_name):
        """
        Verifica si el usuario tiene un permiso específico dentro de su negocio.
        
        Args:
            permission_name (str): Nombre del permiso a verificar (ej: 'can_view_orders')
            
        Returns:
            bool: True si tiene el permiso, False en caso contrario
        """
        # El superusuario siempre tiene todos los permisos
        if self.is_superuser:
            return True
            
        # Si no tiene negocio o rol, no tiene permisos específicos
        if not self.business or not self.business_role:
            return False
            
        # Los administradores tienen todos los permisos en su negocio
        if self.business_role.name.lower() in ['administrador', 'admin']:
            return True
            
        # Para otros roles, verificar el permiso específico
        try:
            permissions = self.business_role.role_permissions
            if not permissions:
                return False
            return getattr(permissions, permission_name, False)
        except (AttributeError, Exception):
            return False
    

class BusinessRole(models.Model):
    """
    Modelo para roles específicos de cada negocio.
    Cada negocio puede tener múltiples roles con diferentes permisos.
    """
    business = models.ForeignKey(
        Business, 
        on_delete=models.CASCADE, 
        related_name='business_roles',
        verbose_name=_("Negocio")
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
            RolePermission.objects.create(role=self, **default_permissions)
    
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
    role = models.OneToOneField(
        BusinessRole, 
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
        return f"Permisos para {self.role}"