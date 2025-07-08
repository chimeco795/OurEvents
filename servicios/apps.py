from django.apps import AppConfig


class ServiciosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'servicios'

 

class ServiciosConfig(AppConfig):
    name = 'servicios'

    def ready(self):
        import servicios.signals
