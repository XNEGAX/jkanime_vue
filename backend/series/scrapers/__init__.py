"""
Scraper Registry — Factory para obtener el scraper según la fuente.
"""
import logging
from typing import Type

logger = logging.getLogger(__name__)

# Registry: se llena cuando se importan las clases concretas
SCRAPER_REGISTRY = {}


def register_scraper(source_name: str, scraper_cls: Type):
    """Registra una clase scraper para una fuente."""
    SCRAPER_REGISTRY[source_name] = scraper_cls


def get_scraper(source: str = "jkanime"):
    """
    Retorna una instancia del scraper para la fuente indicada.
    Si no encuentra la fuente, usa jkanime como fallback.
    """
    from .base import BaseScraper

    cls = SCRAPER_REGISTRY.get(source)
    if not cls:
        logger.warning(f"Scraper para fuente '{source}' no encontrado, usando jkanime como fallback")
        cls = SCRAPER_REGISTRY.get("jkanime")
    if not cls:
        raise ImportError("No hay scraper registrado. ¿Se importaron las clases?")
    return cls()


# Importar las clases concretas para que se registren
from .jkanime import JKanimeScraper  # noqa: E402, F811
from .latanime import LatanimeScraper  # noqa: E402, F811
