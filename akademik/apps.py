from django.apps import AppConfig


class AkademikConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'akademik'

    def ready(self):
        from . import signals  # noqa: F401
