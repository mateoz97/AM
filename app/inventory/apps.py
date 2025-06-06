# REEMPLAZAR TODO EL CONTENIDO DE app/inventory/apps.py
from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app.inventory'
    verbose_name = 'Inventario de Productos'
    
    def ready(self):
        try:
            import app.inventory.signals
        except ImportError:
            pass