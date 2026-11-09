"""
Scraper para YouTube — extrae playlists y videos como series anime.

Implementa BaseScraper para integrarse con el sistema jkanime_vue.
Usa yt-dlp para extraer información de playlists y videos de YouTube.

Notas:
- YouTube no provee enlaces MP4 directos simples: el downloader usa yt-dlp
  para obtener la mejor calidad disponible y el usuario puede descargar
  o el sistema puede guardar la referencia para descarga manual.
- Esta fuente está pensada para series anime que están en playlists de YouTube.
- Los "capítulos" de la serie son los videos de la playlist en orden.
"""

import logging
import re
from typing import Optional

from .base import BaseScraper
from . import register_scraper

logger = logging.getLogger(__name__)

# Prefijos de IDs de playlist conocidos por YouTube. Un video individual mide
# 11 caracteres; las playlists suelen medir 34 y empezar con uno de estos.
_PLAYLIST_PREFIXES = ('PL', 'UU', 'OL', 'LL', 'FL', 'RD')


def _extract_video_id(url: str) -> Optional[str]:
    """Extrae el ID de 11 caracteres de una URL de video de YouTube."""
    match = re.search(
        r'(?:v=|youtu\.be/|/embed/|/shorts/|/live/)([a-zA-Z0-9_-]{11})',
        url,
    )
    return match.group(1) if match else None


def _looks_like_video_id(identifier: str) -> bool:
    """Heuristica: un ID de 11 caracteres que no es prefijo de playlist."""
    if len(identifier) != 11 or not re.fullmatch(r'[a-zA-Z0-9_-]{11}', identifier):
        return False
    return not identifier.startswith(_PLAYLIST_PREFIXES)


class YouTubeScraper(BaseScraper):
    """Scraper para YouTube playlists como series anime."""

    SOURCE_NAME = "youtube"
    BASE_URL = "https://www.youtube.com"
    TIMEOUT = 30

    def _get_ydl_opts(self) -> dict:
        """Opciones base para yt-dlp."""
        return {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'skip_download': True,
        }

    def _extract_playlist_info(self, playlist_url: str) -> Optional[dict]:
        """Extrae información de una playlist de YouTube usando yt-dlp."""
        import yt_dlp

        try:
            ydl_opts = self._get_ydl_opts()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Usar la URL completa de la playlist
                info = ydl.extract_info(playlist_url, download=False)
                if info and 'entries' in info:
                    entries = info['entries'] or []
                    return {
                        'title': info.get('title', 'Playlist de YouTube'),
                        'description': info.get('description', ''),
                        'channel': info.get('channel', ''),
                        'video_count': info.get('playlist_count', len(entries)),
                        'videos': entries,
                    }
                # Sin `entries` no es una playlist: los videos individuales
                # los resuelve `_extract_video_info`.
                return None
        except Exception as e:
            logger.error(f"Error extrayendo playlist YouTube {playlist_url}: {e}")
            return None

    def _extract_playlist_info_by_id(self, playlist_id: str) -> Optional[dict]:
        """Extrae info de playlist usando ID con formato PL..."""
        import yt_dlp

        try:
            # El ID viene completo desde la URL (`list=`); no se le antepone PL.
            yt_playlist_id = playlist_id
            ydl_opts = self._get_ydl_opts()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Usar formato URL de playlist
                playlist_url = f"https://www.youtube.com/playlist?list={yt_playlist_id}"
                info = ydl.extract_info(playlist_url, download=False)
                if info and 'entries' in info:
                    entries = info['entries'] or []
                    return {
                        'title': info.get('title', 'Playlist de YouTube'),
                        'description': info.get('description', ''),
                        'channel': info.get('channel', ''),
                        'video_count': info.get('playlist_count', len(entries)),
                        'videos': entries,
                    }
                return None
        except Exception as e:
            logger.error(f"Error extrayendo playlist por ID {playlist_id}: {e}")
            return None

    def get_all_series(self) -> list[dict]:
        """
        Obtiene todas las series desde una fuente global.

        YouTube no tiene un directorio global como jkanime, por lo que
        retorna lista vacía. Las series se obtienen mediante get_series_info
        con URLs de playlist específicas.
        """
        return []

    def _extract_video_info(self, video_id: str) -> Optional[dict]:
        """Extrae la info de un video individual de YouTube con yt-dlp."""
        import yt_dlp

        try:
            ydl_opts = self._get_ydl_opts()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(
                    f"https://www.youtube.com/watch?v={video_id}", download=False
                )
                if not info:
                    return None
                return {
                    'id': info.get('id', video_id),
                    'title': info.get('title', 'Video de YouTube'),
                    'description': info.get('description', ''),
                    'channel': info.get('channel', ''),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'webpage_url': info.get(
                        'webpage_url', f"https://www.youtube.com/watch?v={video_id}"
                    ),
                }
        except Exception as e:
            logger.error(f"Error extrayendo video YouTube {video_id}: {e}")
            return None

    def _playlist_series_info(self, playlist_id: str, original_url: str = '') -> Optional[dict]:
        """Construye la info de serie a partir de una playlist de YouTube."""
        canonical_url = f"https://www.youtube.com/playlist?list={playlist_id}"
        info = None
        # La URL canonica es la mas fiable; la original puede ser un watch?v=&list=
        for candidate in (canonical_url, original_url):
            if not candidate:
                continue
            info = self._extract_playlist_info(candidate)
            if info:
                break
        if not info:
            info = self._extract_playlist_info_by_id(playlist_id)
        if not info:
            return None

        cover_url = None
        videos = info.get('videos') or []
        if videos:
            vid = videos[0].get('id', '')
            if vid:
                cover_url = f"https://img.youtube.com/vi/{vid}/maxresdefault.jpg"

        return {
            'slug': f"youtube-{playlist_id}",
            'nombre': info.get('title', 'Playlist de YouTube'),
            'url': canonical_url,
            'cover_url': cover_url,
            'estado': 'en_emision',
            'es_pelicula': False,
            'dia_emision': '',
        }

    def _video_series_info(self, video_id: str) -> Optional[dict]:
        """Construye la info de serie para un video individual (1 capitulo)."""
        info = self._extract_video_info(video_id)
        if not info:
            return None

        return {
            'slug': f"youtube-{video_id}",
            'nombre': info.get('title', 'Video de YouTube'),
            'url': f"https://www.youtube.com/watch?v={info.get('id') or video_id}",
            'cover_url': (
                info.get('thumbnail')
                or f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
            ),
            'estado': 'concluido',
            'es_pelicula': False,
            'dia_emision': '',
        }

    def get_series_info(self, url: str) -> Optional[dict]:
        """
        Obtiene info de una serie desde una URL de YouTube.

        Acepta una playlist (serie con varios capitulos) o un video individual
        (serie de un solo capitulo).

        Retorna dict: {slug, nombre, url, cover_url, estado, es_pelicula, dia_emision}
        """
        playlist_match = re.search(r'[?&]list=([a-zA-Z0-9_-]+)', url)
        if playlist_match:
            playlist_id = playlist_match.group(1)
            info = self._playlist_series_info(playlist_id, url)
            if info:
                return info
            # Playlist invalida/privada: si la URL tambien trae un video, se
            # agrega ese video como serie de un capitulo en vez de fallar.
            video_id = _extract_video_id(url)
            if video_id:
                return self._video_series_info(video_id)
            return None

        video_id = _extract_video_id(url)
        if not video_id:
            return None
        return self._video_series_info(video_id)

    def _playlist_episodes(self, playlist_id: str) -> list[dict]:
        """Episodios de una playlist, en el orden en que YouTube la devuelve."""
        original_url = f"https://www.youtube.com/playlist?list={playlist_id}"
        info = self._extract_playlist_info(original_url)
        if not info or not info.get('videos'):
            info = self._extract_playlist_info_by_id(playlist_id)
        if not info or not info.get('videos'):
            return []

        episodes = []
        for idx, video in enumerate(info['videos']):
            video_id = video.get('id', '')
            episodes.append({
                'numero': idx + 1,
                'url': f"https://www.youtube.com/watch?v={video_id}" if video_id else None,
                'timestamp': '',
                'metadata': {
                    'title': video.get('title', f'Episodio {idx + 1}'),
                    'duration': video.get('duration', 0),
                    'video_id': video_id,
                },
            })

        episodes.sort(key=lambda x: x['numero'])
        return episodes

    def _video_episodes(self, video_id: str) -> list[dict]:
        """Un unico episodio para un video individual."""
        info = self._extract_video_info(video_id)
        if not info:
            return []
        real_id = info.get('id') or video_id
        return [{
            'numero': 1,
            'url': f"https://www.youtube.com/watch?v={real_id}",
            'timestamp': '',
            'metadata': {
                'title': info.get('title', 'Video de YouTube'),
                'duration': info.get('duration', 0),
                'video_id': real_id,
            },
        }]

    def get_episodes(self, slug: str) -> list[dict]:
        """
        Obtiene episodios de una serie YouTube.

        El slug tiene formato "youtube-<playlist_id>" o "youtube-<video_id>".
        Intenta primero la variante que corresponde y cae a la otra si falla.
        """
        if not slug.startswith('youtube-'):
            return []

        identifier = slug[len('youtube-'):]
        if not identifier:
            return []

        if _looks_like_video_id(identifier):
            return self._video_episodes(identifier) or self._playlist_episodes(identifier)
        return self._playlist_episodes(identifier) or self._video_episodes(identifier)

    def get_download_urls(self, episode_url: str) -> list[dict]:
        """
        Obtiene URLs de descarga directa para un episodio de YouTube.

        YouTube ya no publica formatos progresivos: imagen y sonido viajan en
        streams DASH separados. La URL de un formato de video suelto se baja sin
        errores y produce un MP4 mudo, que es peor que un fallo porque parece
        una descarga exitosa.

        Por eso este metodo solo devuelve formatos que traigan video Y audio en
        el mismo archivo. Si no hay ninguno (el caso normal hoy), devuelve una
        lista vacia: la descarga real la hace `tasks._descargar_youtube`, que
        baja ambos streams con yt-dlp y los une con ffmpeg.

        Retorna lista de dicts: {server, url, size, resolved}
        """
        import yt_dlp

        try:
            video_id = _extract_video_id(episode_url)
            if not video_id:
                return []

            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(episode_url, download=False)

            mp4_formats = [
                f for f in info.get('formats', [])
                if f.get('ext') == 'mp4'
                and f.get('url', '').startswith('https')
                and f.get('vcodec', 'none') != 'none'
                # Sin esta condicion se devuelven streams de solo video y la
                # descarga termina en un MP4 sin audio.
                and f.get('acodec', 'none') != 'none'
            ]

            if not mp4_formats:
                logger.info(
                    "YouTube sin formatos progresivos (video+audio) para %s; "
                    "la descarga va por yt-dlp + ffmpeg", episode_url
                )
                return []

            mp4_formats.sort(key=lambda f: f.get('height', 0), reverse=True)

            results = []
            for fmt in mp4_formats[:5]:  # Top 5 formatos
                url = fmt.get('url', '')
                filesize = fmt.get('filesize') or fmt.get('filesize_approx')
                results.append({
                    'server': 'YouTube',
                    'url': url,
                    'size': _format_size(filesize) if filesize else 'desconocido',
                    'resolved': url.startswith('https://'),
                })

            return results

        except Exception as e:
            logger.error(f"Error getting download URLs YouTube: {e}")
            return []


def _format_size(size_bytes: Optional[int]) -> str:
    """Formatea tamaño en bytes a string legible."""
    if not size_bytes:
        return 'desconocido'
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024**2:.1f} MB"
    return f"{size_bytes / 1024**3:.2f} GB"


# Registrar el scraper en el registry global
register_scraper("youtube", YouTubeScraper)