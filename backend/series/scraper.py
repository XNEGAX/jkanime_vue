"""
Scraper Compatibility Shim — mantiene compatibilidad con imports antiguos.
Todo el código migró a scrapers/jkanime.py, scrapers/latanime.py, etc.
Este archivo expone las funciones y constantes de JKanimeScraper para
no romper imports existentes durante la transición.
"""
import logging

# Re-exportar para compatibilidad con código que hace `from . import scraper`
from .scrapers.jkanime import JKanimeScraper
from .scrapers import get_scraper
from .scrapers.resolvers import resolve_video_url

logger = logging.getLogger(__name__)

# Instancia singleton para compatibilidad
_jk_instance = JKanimeScraper()

# Re-exportar constantes
BASE_URL = JKanimeScraper.BASE_URL
SERVER_PRIORITY = JKanimeScraper.SERVER_PRIORITY
REFERER_MAP = JKanimeScraper.REFERER_MAP

# Re-exportar funciones públicas (delegan a la instancia)
get_all_series_from_jkanime = _jk_instance.get_all_series
get_episodes_for_series = _jk_instance.get_episodes
get_series_info_by_url = _jk_instance.get_series_info
get_download_urls = _jk_instance.get_download_urls
check_episode_exists = _jk_instance.check_episode_exists if hasattr(_jk_instance, 'check_episode_exists') else None
