"""
Scraper Registry — Factory para obtener el scraper según la fuente.
"""
import logging
import threading
from typing import Type

logger = logging.getLogger(__name__)

# Registry: se llena cuando se importan las clases concretas
SCRAPER_REGISTRY = {}

# Instancias vivas, una por fuente. Sin esto `get_scraper()` devolvía un objeto
# nuevo en cada llamada, así que la sesión cloudscraper (cookies + cf_clearance
# +.connection pool) moría con la llamada y cada scraper método pagaba de nuevo
# el desafío de Cloudflare. Con la instancia memoizada, la sesión sobrevive a
# la request y la comparten los workers en background.
_SCRAPER_INSTANCES = {}
_SCRAPER_INSTANCES_LOCK = threading.Lock()


def register_scraper(source_name: str, scraper_cls: Type):
    """Registra una clase scraper para una fuente."""
    SCRAPER_REGISTRY[source_name] = scraper_cls


def get_scraper(source: str = "jkanime"):
    """
    Retorna una instancia del scraper para la fuente indicada.
    Si no encuentra la fuente, usa jkanime como fallback.

    Siempre devuelve la MISMA instancia para la misma fuente, para que el
    estado de sesión sobreviva entre llamadas. Las clases scraper no guardan
    estado por llamada (todo es local a cada método), así que compartirla entre
    threads es seguro.
    """
    from .base import BaseScraper  # noqa: F401

    cls = SCRAPER_REGISTRY.get(source)
    if not cls:
        logger.warning(f"Scraper para fuente '{source}' no encontrado, usando jkanime como fallback")
        cls = SCRAPER_REGISTRY.get("jkanime")
    if not cls:
        raise ImportError("No hay scraper registrado. ¿Se importaron las clases?")

    # La clave es el SOURCE_NAME de la clase resuelta, no el argumento: asi un
    # source desconocido y "jkanime" terminan compartiendo la misma instancia.
    key = getattr(cls, "SOURCE_NAME", source)

    instance = _SCRAPER_INSTANCES.get(key)
    if instance is not None:
        return instance

    with _SCRAPER_INSTANCES_LOCK:
        instance = _SCRAPER_INSTANCES.get(key)
        if instance is None:
            instance = cls()
            _SCRAPER_INSTANCES[key] = instance
        return instance


# Importar las clases concretas para que se registren
from .jkanime import JKanimeScraper  # noqa: E402, F811
from .latanime import LatanimeScraper  # noqa: E402, F811
from .hentaidtv import HentaidTVScraper  # noqa: E402, F811
from .youtube import YouTubeScraper  # noqa: E402, F811
from .animeflv import AnimeFLVScraper  # noqa: E402, F811
