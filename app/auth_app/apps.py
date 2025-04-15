from django.apps import AppConfig


class AuthAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app.auth_app'
    verbose_name = 'Usuarios y Negocios'
    
    def ready(self):
        try:
            import app.auth_app.signals
            print("Signals de auth_app cargados correctamente")
        except Exception as e:
            print(f"Error al cargar signals: {str(e)}")
