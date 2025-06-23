# app/roles/models/main_role.py
from django.db import models
from django.utils.translation import gettext_lazy as _


class MainRole(models.Model):
    """
    Modelo para roles del sistema principal.
    Define los tipos de usuarios en la aplicación global (cliente vs propietario de negocio).
    """
    ROLE_TYPES = (
        ('client', _('Cliente')),
        ('business_owner', _('Propietario de Negocio')),
    )
    
    name = models.CharField(
        _("Nombre del rol"), 
        max_length=50, 
        choices=ROLE_TYPES,
        unique=True
    )
    display_name = models.CharField(_("Nombre para mostrar"), max_length=100)
    description = models.TextField(_("Descripción"), blank=True, null=True)
    is_active = models.BooleanField(_("Activo"), default=True)
    created_at = models.DateTimeField(_("Fecha de creación"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Fecha de actualización"), auto_now=True)
    
    class Meta:
        verbose_name = _("Rol principal")
        verbose_name_plural = _("Roles principales")
        ordering = ['name']
    
    def __str__(self):
        return self.display_name
    
    @classmethod
    def get_client_role(cls):
        """Obtiene el rol de cliente"""
        role, created = cls.objects.get_or_create(
            name='client',
            defaults={
                'display_name': 'Cliente',
                'description': 'Usuario cliente del sistema'
            }
        )
        return role
    
    @classmethod
    def get_business_owner_role(cls):
        """Obtiene el rol de propietario de negocio"""
        role, created = cls.objects.get_or_create(
            name='business_owner',
            defaults={
                'display_name': 'Propietario de Negocio',
                'description': 'Usuario que posee uno o más negocios'
            }
        )
        return role


class MainRolePermission(models.Model):
    """
    Permisos para roles del sistema principal.
    Define qué pueden hacer los usuarios según su rol principal.
    """
    
    main_role = models.OneToOneField(
        'roles.MainRole',
        on_delete=models.CASCADE,
        related_name='permissions',
        verbose_name=_("Rol principal")
    )
    
    # Permisos generales del sistema
    can_create_business = models.BooleanField(_("Puede crear negocios"), default=False)
    can_manage_own_businesses = models.BooleanField(_("Puede gestionar sus negocios"), default=False)
    can_create_posts = models.BooleanField(_("Puede crear publicaciones"), default=True)
    can_comment_posts = models.BooleanField(_("Puede comentar publicaciones"), default=True)
    can_like_posts = models.BooleanField(_("Puede dar me gusta"), default=True)
    can_follow_businesses = models.BooleanField(_("Puede seguir negocios"), default=True)
    can_view_business_profiles = models.BooleanField(_("Puede ver perfiles de negocios"), default=True)
    
    # Permisos administrativos (para futuras funcionalidades)
    can_moderate_content = models.BooleanField(_("Puede moderar contenido"), default=False)
    can_access_admin_panel = models.BooleanField(_("Puede acceder al panel admin"), default=False)
    
    created_at = models.DateTimeField(_("Fecha de creación"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Fecha de actualización"), auto_now=True)
    
    class Meta:
        verbose_name = _("Permisos de rol principal")
        verbose_name_plural = _("Permisos de roles principales")
    
    def __str__(self):
        return f"Permisos para {self.main_role.display_name}"
    
    def save(self, *args, **kwargs):
        """Configurar permisos por defecto según el tipo de rol"""
        if not self.pk:  # Solo en creación
            if self.main_role.name == 'business_owner':
                self.can_create_business = True
                self.can_manage_own_businesses = True
            elif self.main_role.name == 'client':
                self.can_create_business = False
                self.can_manage_own_businesses = False
        
        super().save(*args, **kwargs)