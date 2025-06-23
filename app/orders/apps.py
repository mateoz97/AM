from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app.orders'
    verbose_name = 'Órdenes'
    
    def ready(self):
        """Importar signals cuando la app esté lista"""
        try:
            import app.orders.signals
        except ImportError:
            pass
