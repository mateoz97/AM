# CREAR NUEVO ARCHIVO: app/inventory/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
import logging

from .models import Product, StockMovement, ProductCategory

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Product)
def log_product_changes(sender, instance, created, **kwargs):
    """Log de cambios en productos"""
    action = "created" if created else "updated"
    logger.info(f"Product {action}: {instance.name} (ID: {instance.id}) - Business: {instance.business.name}")
    
    # Invalidar cache de categorías si cambió la categoría
    if not created and instance.category:
        cache_key = f"categories_business_{instance.business.id}"
        cache.delete(cache_key)


@receiver(post_save, sender=StockMovement)
def verify_stock_consistency(sender, instance, created, **kwargs):
    """Verificar consistencia de stock"""
    if created:
        product = instance.product
        expected_stock = instance.new_stock
        if product.stock != expected_stock:
            logger.warning(
                f"Stock inconsistency detected for product {product.name}: "
                f"Expected {expected_stock}, actual {product.stock}"
            )


@receiver(post_save, sender=ProductCategory)
@receiver(post_delete, sender=ProductCategory)
def invalidate_category_cache(sender, instance, **kwargs):
    """Invalidar cache de categorías cuando se modifica una categoría"""
    cache_key = f"categories_business_{instance.business.id}"
    cache.delete(cache_key)