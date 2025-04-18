# Django
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

class Business(models.Model):
    name = models.CharField(_("Nombre"), max_length=255, unique=True)
    from django.conf import settings
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="owned_businesses",
        null=True,
        blank=True,
        verbose_name=_("Propietario")
    )
    is_main_business = models.BooleanField(_("Es negocio principal"), default=True)
    co_owners = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="co_owned_businesses",
        blank=True,
        verbose_name=_("Co-propietarios")
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
        is_new = self.pk is None
        if self.pk is not None:
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
            # Si el antiguo propietario tenía este negocio como su negocio principal, 
            # lo movemos a co-propietario si lo desea (o lo quitamos)
            if old_owner.business == self:
                # Opción 1: Quitar completamente
                old_owner.business = None
                old_owner.save(update_fields=['business'])
                
                # Opción 2: Mover a co-propietario (descomenta si lo deseas)
                # self.co_owners.add(old_owner)
        
        # Actualizar el nuevo propietario si existe
        if self.owner:
            # Buscar el rol de administrador para este negocio
            from app.roles.models.role import BusinessRole
            admin_role = BusinessRole.objects.filter(
                business=self, 
                name="Admin"
            ).first()
            
            # Si no existe el rol de administrador, crearlo
            if not admin_role:
                from app.roles.services.role_service import BusinessRoleService
                roles = BusinessRoleService.create_business_roles(self)
                admin_role = roles.get("Admin")
            
            # Verificar si el usuario ya tiene un negocio asignado
            has_other_business = self.owner.business and self.owner.business.id != self.id
            
            # Si no tiene otro negocio o este negocio tiene prioridad, asignar directamente
            if not has_other_business or kwargs.get('is_primary_business', True):
                self.owner.business = self
                self.owner.business_role = admin_role
                self.owner.save(update_fields=['business', 'business_role'])
            # Si tiene otro negocio y este no tiene prioridad, agregarlo como co-propietario
            elif has_other_business:
                self.co_owners.add(self.owner)
            
            if is_new:
                try:
                    from app.business.services.business_service import DatabaseService
                    print(f"Intentando crear base de datos para negocio: {self.name} ({self.id})")
                    success = DatabaseService.create_business_database(self)
                    if not success:
                        print(f"Advertencia: No se pudo crear la base de datos para el negocio {self.name}")
                except Exception as e:
                    print(f"Error al crear base de datos para negocio {self.name}: {str(e)}")
    
    def delete(self, using=None, keep_parents=False):
        """
        Sobrescribe el método delete para eliminar la base de datos asociada al negocio
        """
        # Nombre de la base de datos asociada
        db_name = f"business_{self.name}"
        db_path = None
        
        # Verificar si la base de datos existe en la configuración
        from django.conf import settings
        if db_name in settings.DATABASES:
            db_path = settings.DATABASES[db_name]['NAME']
            # Eliminar la base de datos de la configuración
            del settings.DATABASES[db_name]
            print(f"Eliminada configuración de base de datos {db_name}")
        
        # Llamar al método delete original
        result = super().delete(using=using, keep_parents=keep_parents)
        
        # Eliminar físicamente el archivo de la base de datos
        if db_path:
            import os
            if os.path.exists(db_path):
                try:
                    os.remove(db_path)
                    print(f"Eliminado archivo de base de datos {db_path}")
                except Exception as e:
                    print(f"Error al eliminar archivo de base de datos {db_path}: {str(e)}")
        
        return result
    
    def soft_delete(self):
        """
        Realiza una eliminación lógica del negocio sin eliminar la base de datos
        """
        self.is_active = False
        self.save(update_fields=['is_active'])
        return True

class BusinessJoinRequest(models.Model):
    user = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE, related_name='join_requests')
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE, related_name='join_requests')
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pendiente'),
        ('approved', 'Aprobada'),
        ('rejected', 'Rechazada')
    ], default='pending')
    message = models.TextField(_("Mensaje"), blank=True, null=True)  # Añadir este campo
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('user', 'business')

class BusinessInvitation(models.Model):
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE, related_name='invitations')
    created_by = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE, related_name='created_invitations')
    token = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    role = models.ForeignKey('roles.BusinessRole', on_delete=models.SET_NULL, null=True, blank=True)
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _("Invitación")
        verbose_name_plural = _("Invitaciones")
    
    def is_valid(self):
        return not self.used and self.expires_at > timezone.now()
    
    def save(self, *args, **kwargs):
        if not self.token:
            import secrets
            self.token = secrets.token_urlsafe(32)
        if not self.expires_at:
            from django.utils import timezone
            from datetime import timedelta
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

class BusinessBranch(models.Model):
    """
    Modelo para representar sucursales de un negocio principal
    """
    main_business = models.ForeignKey(
        'business.Business',
        on_delete=models.CASCADE,
        related_name='branches'
    )
    name = models.CharField(_("Nombre"), max_length=255)
    description = models.TextField(_("Descripción"), null=True, blank=True)
    address = models.CharField(_("Dirección"), max_length=255, null=True, blank=True)
    manager = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_branches'
    )
    is_active = models.BooleanField(_("Activa"), default=True)
    created_at = models.DateTimeField(_("Fecha de creación"), auto_now_add=True)
    
    class Meta:
        verbose_name = _("Sucursal")
        verbose_name_plural = _("Sucursales")
        unique_together = ('main_business', 'name')
        
    def __str__(self):
        return f"{self.main_business.name} - {self.name}"
