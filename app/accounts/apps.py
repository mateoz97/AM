# Django
from django.apps import AppConfig


class AuthAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app.accounts'
    verbose_name = 'Usuarios y Negocios'
    
    def ready(self):
        try:
            import app.accounts.signals
            print("Signals de accounts cargados correctamente")
        except Exception as e:
            print(f"Error al cargar signals: {str(e)}")
