import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class SeriesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'series'
    verbose_name = 'AnimeWing'

    def ready(self):
        """Arranca los workers threading al iniciar Django (mismo proceso)."""
        # Evitar que se ejecute dos veces en modo reload del dev server
        if hasattr(self.__class__, '_workers_started'):
            return
        self.__class__._workers_started = True

        try:
            from .task_runner import start_workers
            start_workers(count=50)
            logger.info("Task runner: 50 workers iniciados desde AppConfig.ready()")
        except Exception as e:
            logger.exception(f"Error iniciando task runner: {e}")
