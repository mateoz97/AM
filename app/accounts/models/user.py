# Django
from django.contrib.auth.models import AbstractUser, Permission
from django.db import models
from django.utils.translation import gettext_lazy as _



class CustomUser(AbstractUser):  
    business = models.ForeignKey(
        "business.Business", 
        on_delete=models.SET_NULL, 
        related_name="members",
        null=True, 
        blank=True,
        verbose_name=_("Negocio")
    )

    business_role = models.ForeignKey(
        "roles.BusinessRole",
        on_delete=models.SET_NULL,
        related_name="users",
        null=True,
        blank=True,
        verbose_name=_("Rol de negocio")
    )

    user_permissions = models.ManyToManyField(
        Permission,
        related_name="accounts_users_permissions",
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
        role_name = self.business_role.name if self.business_role else _('Sin rol')
        business_name = self.business.name if self.business else _('Sin negocio')
        return f"{self.get_full_name() or self.username} - {role_name} ({business_name})"
    
    def has_role(self, role_name):
        """Verifica si el usuario tiene un rol específico"""
        if not self.business_role:
            return False
        
        return self.business_role.name.lower() == role_name.lower()
    
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
        if self.business_role.name.lower() in ['admin']:
            return True
            
        # Para otros roles, verificar el permiso específico
        try:
            permissions = self.business_role.role_permissions
            if not permissions:
                return False
            return getattr(permissions, permission_name, False)
        except (AttributeError, Exception):
            return False
        