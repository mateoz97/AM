# Django
from django.contrib.auth.models import AbstractUser, Permission
from django.db import models
from django.utils.translation import gettext_lazy as _



class CustomUser(AbstractUser):
    USER_TYPES = (
        ('client', _('Cliente')),
        ('business_owner', _('Propietario de Negocio')),
    )
    
    # Tipo de usuario en el sistema principal
    user_type = models.CharField(
        _("Tipo de usuario"),
        max_length=20,
        choices=USER_TYPES,
        default='client'
    )
    
    # Rol principal en el sistema (referencia al nuevo sistema de roles)
    main_role = models.ForeignKey(
        "roles.MainRole",
        on_delete=models.SET_NULL,
        related_name="users",
        null=True,
        blank=True,
        verbose_name=_("Rol principal")
    )
    
    # Negocio actual activo (para cambio de perfil)
    current_business = models.ForeignKey(
        "business.Business", 
        on_delete=models.SET_NULL, 
        related_name="active_users",
        null=True, 
        blank=True,
        verbose_name=_("Negocio activo actual")
    )

    # Rol actual en el negocio activo
    current_business_role = models.ForeignKey(
        "roles.BusinessRole",
        on_delete=models.SET_NULL,
        related_name="active_users",
        null=True,
        blank=True,
        verbose_name=_("Rol actual de negocio")
    )
    
    # Compatibilidad con código existente
    @property
    def business(self):
        """Compatibilidad: retorna el negocio actual"""
        return self.current_business
    
    @business.setter
    def business(self, value):
        """Compatibilidad: establece el negocio actual"""
        self.current_business = value
    
    @property 
    def business_role(self):
        """Compatibilidad: retorna el rol actual"""
        return self.current_business_role
    
    @business_role.setter
    def business_role(self, value):
        """Compatibilidad: establece el rol actual"""
        self.current_business_role = value

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
    
    def get_owned_businesses(self):
        """Retorna todos los negocios que posee este usuario"""
        return self.owned_businesses.filter(is_active=True)
    
    def get_co_owned_businesses(self):
        """Retorna todos los negocios donde es co-propietario"""
        return self.co_owned_businesses.filter(is_active=True)
    
    def get_available_businesses(self):
        """Retorna todos los negocios a los que tiene acceso (propios + co-propios + empleado)"""
        from app.business.models.business import Business
        
        owned = self.get_owned_businesses()
        co_owned = self.get_co_owned_businesses()
        
        # Negocios donde es empleado (tiene rol asignado)
        employee_businesses = Business.objects.filter(
            business_roles__users=self,
            is_active=True
        ).distinct()
        
        # Combinar todos
        all_businesses = owned.union(co_owned, employee_businesses)
        return all_businesses
    
    def can_switch_to_business(self, business_id):
        """Verifica si el usuario puede cambiar a un negocio específico"""
        available_businesses = self.get_available_businesses()
        return available_businesses.filter(id=business_id).exists()
    
    def switch_to_business(self, business_id):
        """Cambia el perfil activo a un negocio específico"""
        if not self.can_switch_to_business(business_id):
            return False, "No tienes acceso a este negocio"
        
        from app.business.models.business import Business
        try:
            business = Business.objects.get(id=business_id)
            
            # Determinar el rol apropiado
            if business.owner == self:
                # Es propietario, buscar rol de Admin
                from app.roles.models.role import BusinessRole
                role = BusinessRole.objects.filter(
                    business=business,
                    name__in=['Admin', 'Owner', 'Propietario']
                ).first()
            elif self in business.co_owners.all():
                # Es co-propietario, buscar rol de Manager
                from app.roles.models.role import BusinessRole
                role = BusinessRole.objects.filter(
                    business=business,
                    name__in=['Manager', 'Gerente']
                ).first()
            else:
                # Es empleado, usar rol asignado
                from app.roles.models.role import BusinessRole
                role = BusinessRole.objects.filter(
                    business=business,
                    users=self
                ).first()
            
            # Actualizar usuario
            self.current_business = business
            self.current_business_role = role
            self.user_type = 'business_owner' if business.owner == self else self.user_type
            self.save(update_fields=['current_business', 'current_business_role', 'user_type'])
            
            return True, f"Cambiado al negocio {business.name}"
            
        except Business.DoesNotExist:
            return False, "Negocio no encontrado"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def switch_to_personal_profile(self):
        """Cambia a perfil personal (sin negocio activo)"""
        self.current_business = None
        self.current_business_role = None
        # Solo cambiar a client si no es propietario de negocios
        if not self.get_owned_businesses().exists():
            self.user_type = 'client'
            self.ensure_main_role()
        self.save(update_fields=['current_business', 'current_business_role', 'user_type'])

    def has_business_permission(self, permission_name):
        """
        Verifica si el usuario tiene un permiso específico dentro de su negocio actual.
        
        Args:
            permission_name (str): Nombre del permiso a verificar (ej: 'can_view_orders')
            
        Returns:
            bool: True si tiene el permiso, False en caso contrario
        """
        # El superusuario siempre tiene todos los permisos
        if self.is_superuser:
            return True
            
        # Si no tiene negocio o rol actual, no tiene permisos específicos
        if not self.current_business or not self.current_business_role:
            return False
            
        # Los propietarios tienen todos los permisos en su negocio
        if self.current_business.owner == self:
            return True
            
        # Para otros roles, verificar el permiso específico
        try:
            permissions = self.current_business_role.role_permissions
            if not permissions:
                return False
            return getattr(permissions, permission_name, False)
        except (AttributeError, Exception):
            return False
    
    def ensure_main_role(self):
        """Asegura que el usuario tenga un rol principal asignado"""
        if not self.main_role:
            from app.roles.models.main_role import MainRole
            
            if self.user_type == 'business_owner':
                self.main_role = MainRole.get_business_owner_role()
            else:
                self.main_role = MainRole.get_client_role()
            
            self.save(update_fields=['main_role'])
    
    def has_main_permission(self, permission_name):
        """
        Verifica si el usuario tiene un permiso específico en el sistema principal.
        
        Args:
            permission_name (str): Nombre del permiso a verificar
            
        Returns:
            bool: True si tiene el permiso, False en caso contrario
        """
        # Superusuario siempre tiene permisos
        if self.is_superuser:
            return True
        
        # Asegurar que tenga rol principal
        self.ensure_main_role()
        
        # Verificar permiso en el rol principal
        try:
            if hasattr(self.main_role, 'permissions'):
                permissions = self.main_role.permissions
                return getattr(permissions, permission_name, False)
            return False
        except (AttributeError, Exception):
            return False
    
    def can_create_business(self):
        """Verifica si el usuario puede crear negocios"""
        return self.has_main_permission('can_create_business')
    
    def can_manage_own_businesses(self):
        """Verifica si el usuario puede gestionar sus propios negocios"""
        return self.has_main_permission('can_manage_own_businesses')
    
    def promote_to_business_owner(self):
        """Promueve al usuario a propietario de negocio"""
        from app.roles.models.main_role import MainRole
        
        self.user_type = 'business_owner'
        self.main_role = MainRole.get_business_owner_role()
        self.save(update_fields=['user_type', 'main_role'])
        
        return True
    
    def save(self, *args, **kwargs):
        """Override save to ensure main role consistency"""
        # Asegurar que el rol principal corresponda al tipo de usuario
        if self.user_type and not self.main_role:
            self.ensure_main_role()
        
        super().save(*args, **kwargs)
        