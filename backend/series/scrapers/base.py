"""
BaseScraper — clase abstracta para todos los scrapers de fuentes de anime.
"""
from abc import ABC, abstractmethod
from typing import Optional


class BaseScraper(ABC):
    """Interfaz común que deben implementar todos los scrapers."""

    BASE_URL: str
    SOURCE_NAME: str = "unknown"
    SERVER_PRIORITY: list = []
    REFERER_MAP: dict = {}

    @abstractmethod
    def get_all_series(self) -> list[dict]:
        """
        Obtiene todas las series disponibles.
        Retorna lista de dicts: {slug, nombre, url, cover_url}
        """
        ...

    @abstractmethod
    def get_series_info(self, url: str) -> Optional[dict]:
        """
        Obtiene info de una serie desde su URL directa.
        Retorna dict: {slug, nombre, cover_url, estado, es_pelicula, dia_emision}
        o None si falla.
        """
        ...

    @abstractmethod
    def get_episodes(self, slug: str) -> list[dict]:
        """
        Obtiene todos los episodios de una serie.
        Retorna lista de dicts: {numero, url, timestamp}
        """
        ...

    @abstractmethod
    def get_download_urls(self, episode_url: str) -> list[dict]:
        """
        Obtiene las URLs de descarga para un episodio.
        Retorna lista de dicts: {server, url, size}
        ya ordenados por SERVER_PRIORITY.
        """
        ...
