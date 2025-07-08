# app/business/models/business.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.conf import settings

class Business(models.Model):
    BUSINESS_TYPES = (
        ('restaurant', _('Restaurante')),
        ('retail', _('Tienda de venta al por menor')),
        ('service', _('Servicio')),
        ('manufacturing', _('Manufactura')),
        ('technology', _('Tecnología')),
        ('other', _('Otro')),
    )
    
    name = models.CharField(_("Nombre"), max_length=255, unique=True)
    business_type = models.CharField(
        _("Tipo de negocio"),
        max_length=20,
        choices=BUSINESS_TYPES,
        default='restaurant',
        help_text=_("Tipo de negocio que determina el modelo de datos específico")
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="owned_businesses",
        null=True,
        blank=True,
        verbose_name=_("Propietario")
    )
    is_main_business = models.BooleanField(_("Es negocio principal"), default=True)
    # ✅ Campo co_owners corregido
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
        """Retorna todos los usuarios activos del negocio (propietario + co-propietarios + empleados)"""
        from app.accounts.models.user import CustomUser
        
        # Obtener propietario
        members = []
        if self.owner:
            members.append(self.owner)
        
        # Obtener co-propietarios
        members.extend(list(self.co_owners.filter(is_active=True)))
        
        # Obtener empleados (usuarios con roles en este negocio)
        employees = CustomUser.objects.filter(
            current_business_role__business=self,
            is_active=True
        ).exclude(
            id__in=[member.id for member in members]
        )
        members.extend(list(employees))
        
        return members
    
    def is_owner(self, user):
        """Verifica si el usuario es propietario del negocio"""
        return self.owner == user
    
    def is_co_owner(self, user):
        """Verifica si el usuario es co-propietario del negocio"""
        return user in self.co_owners.all()
    
    def has_access(self, user):
        """Verifica si el usuario tiene acceso al negocio"""
        return (
            self.is_owner(user) or 
            self.is_co_owner(user) or 
            user in [member for member in self.get_active_members()]
        )
    
    def save(self, *args, **kwargs):
        # Código existente para manejar el nombre
        if self.name:
            self.name = self.name.replace(" ", "_")
        
        # Detectar si es un nuevo negocio
        is_new = self.pk is None
        
        # Guardar primero el negocio
        super().save(*args, **kwargs)
        
        # Si es un negocio nuevo, crear su base de datos
        if is_new:
            try:
                from app.business.services.business_service import DatabaseService
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"Creando base de datos para negocio: {self.name} (ID: {self.id})")
                success = DatabaseService.create_business_database(self)
                if not success:
                    logger.warning(f"⚠️ Advertencia: No se pudo crear la base de datos para el negocio {self.name}")
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"❌ Error al crear base de datos para negocio {self.name}: {str(e)}")
    
    def delete(self, *args, **kwargs):
        """Override delete para eliminar también el esquema de base de datos"""
        business_id = self.id
        business_name = self.name
        
        try:
            from app.business.services.business_service import DatabaseService
            import logging
            logger = logging.getLogger(__name__)
            
            logger.info(f"Eliminando negocio: {business_name} (ID: {business_id})")
            
            # Eliminar el esquema de base de datos primero
            if business_id:
                success = DatabaseService.delete_business_schema(business_id)
                if success:
                    logger.info(f"✅ Esquema eliminado exitosamente para negocio {business_name}")
                else:
                    logger.warning(f"⚠️ No se pudo eliminar el esquema para negocio {business_name}")
            
            # Eliminar el negocio de la base de datos
            super().delete(*args, **kwargs)
            logger.info(f"✅ Negocio {business_name} eliminado exitosamente")
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"❌ Error al eliminar negocio {business_name}: {str(e)}")
            raise  # Re-lanzar la excepción para que el admin muestre el error

class BusinessJoinRequest(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='join_requests'
    )
    business = models.ForeignKey(
        Business, 
        on_delete=models.CASCADE, 
        related_name='join_requests'
    )
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pendiente'),
        ('approved', 'Aprobada'),
        ('rejected', 'Rechazada')
    ], default='pending')
    message = models.TextField(_("Mensaje"), blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('user', 'business')

class BusinessInvitation(models.Model):
    business = models.ForeignKey(
        Business, 
        on_delete=models.CASCADE, 
        related_name='invitations'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='created_invitations'
    )
    token = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    role = models.ForeignKey(
        'roles.BusinessRole', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
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
            from datetime import timedelta
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

class BusinessBranch(models.Model):
    """
    Modelo para representar sucursales de un negocio principal
    """
    main_business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='branches'
    )
    name = models.CharField(_("Nombre"), max_length=255)
    description = models.TextField(_("Descripción"), null=True, blank=True)
    address = models.CharField(_("Dirección"), max_length=255, null=True, blank=True)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
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