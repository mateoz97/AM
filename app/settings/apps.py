from django.apps import AppConfig


class SettingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app.settings'
    verbose_name = 'Configuraciones'
    
    def ready(self):
        pass