# app/inventory/models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from app.accounts.models.user import CustomUser
from app.business.models.business import Business

class Product(models.Model):
    """Modelo para productos del inventario"""
    business = models.ForeignKey(
        Business, 
        on_delete=models.CASCADE, 
        related_name='products',
        verbose_name=_("Negocio")
    )
    name = models.CharField(_("Nombre"), max_length=100)
    description = models.TextField(_("Descripción"), blank=True, null=True)
    price = models.DecimalField(_("Precio"), max_digits=10, decimal_places=2)
    category = models.CharField(_("Categoría"), max_length=50, blank=True, null=True)
    image = models.ImageField(_("Imagen"), upload_to='products/', blank=True, null=True)
    stock = models.IntegerField(_("Stock"), default=0)
    is_active = models.BooleanField(_("Activo"), default=True)
    created_at = models.DateTimeField(_("Fecha de creación"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Fecha de actualización"), auto_now=True)
    created_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        related_name='created_products',
        verbose_name=_("Creado por"),
        null=True, 
        blank=True
    )
    
    class Meta:
        verbose_name = _("Producto")
        verbose_name_plural = _("Productos")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['business', 'is_active']),
            models.Index(fields=['business', 'category']),
            models.Index(fields=['created_at']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(price__gt=0), 
                name='positive_price'
            ),
            models.CheckConstraint(
                check=models.Q(stock__gte=0), 
                name='non_negative_stock'
            ),
        ]
        
    def __str__(self):
        return f"{self.name} - {self.business.name}"
    
    def save(self, *args, **kwargs):
        # Si es un nuevo producto y tiene stock negativo, establecer a 0
        if self.stock < 0:
            self.stock = 0
        super().save(*args, **kwargs)
    
    

class ProductCategory(models.Model):
    """Modelo para categorías de productos"""
    business = models.ForeignKey(
        Business, 
        on_delete=models.CASCADE,
        related_name='product_categories',
        verbose_name=_("Negocio")
    )
    name = models.CharField(_("Nombre"), max_length=50)
    description = models.TextField(_("Descripción"), blank=True, null=True)
    is_active = models.BooleanField(_("Activa"), default=True)
    
    class Meta:
        verbose_name = _("Categoría de Producto")
        verbose_name_plural = _("Categorías de Productos")
        unique_together = ('business', 'name')
        
    def __str__(self):
        return f"{self.name} - {self.business.name}"
        
class StockMovement(models.Model):
    """Modelo para registrar movimientos de stock"""
    MOVEMENT_TYPES = (
        ('add', _('Entrada')),
        ('remove', _('Salida')),
        ('adjustment', _('Ajuste')),
    )
    
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE,
        related_name='stock_movements',
        verbose_name=_("Producto")
    )
    movement_type = models.CharField(
        _("Tipo de movimiento"), 
        max_length=20, 
        choices=MOVEMENT_TYPES
    )
    quantity = models.IntegerField(_("Cantidad"))
    previous_stock = models.IntegerField(_("Stock anterior"))
    new_stock = models.IntegerField(_("Nuevo stock"))
    notes = models.TextField(_("Notas"), blank=True, null=True)
    created_at = models.DateTimeField(_("Fecha"), auto_now_add=True)
    created_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        related_name='stock_movements',
        verbose_name=_("Realizado por"),
        null=True, 
        blank=True
    )
    
    class Meta:
        verbose_name = _("Movimiento de Stock")
        verbose_name_plural = _("Movimientos de Stock")
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.get_movement_type_display()} de {self.quantity} - {self.product.name}"