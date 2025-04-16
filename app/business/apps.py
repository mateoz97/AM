from django.apps import AppConfig


class BusinessConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app.business'
    verbose_name = 'Negocios'
    
    def ready(self):
        try:
            import app.business.signals
            print("Signals de accounts cargados correctamente")
        except Exception as e:
            print(f"Error al cargar signals: {str(e)}")
