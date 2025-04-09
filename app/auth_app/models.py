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