# app/settings/apps.py
from django.apps import AppConfig


class SettingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app.settings'
    verbose_name = 'Configuraciones'
    
    def ready(self):
        import app.settings.signals  # Importar señales si las creamos