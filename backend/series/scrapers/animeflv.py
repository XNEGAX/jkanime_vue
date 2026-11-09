"""
Scraper para AnimeFLV — implementa BaseScraper.

El sitio rota de dominio (`animeflv.one` redirige a `vww.animeflv.one`), por eso
el host base se puede pisar con `ANIMEFLV_BASE_URL` y los GET siguen redirects.

Estructura:
  - Directorio: https://<host>/animes?pag=<n>
  - Serie:      https://<host>/anime/<slug>
  - Episodio:   https://<host>/ver/<slug>-<numero>[-<codigo>]

La lista de episodios vive en el JS inline `var eps = [["<numero>","<flag>","<codigo>"], ...]`.
Cada pagina de episodio trae sus descargas en `div.dwn[data-dwn]`, un JSON con
las URLs reales de descarga.
"""
import os
import re
import json
import logging
import threading
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from .base import BaseScraper
from .cache import shared_scraper_session
from .resolvers import resolve_video_url
from . import register_scraper

logger = logging.getLogger(__name__)

# Cuantos hosts reconoce el scrapers por el dominio del link de descarga. El
# valor DEBE coincidir exacto con las claves de `resolvers.RESOLVER_MAP`, si no
# el resolver queda desactivado en silencio y el link se entrega sin resolver.
_DOWNLOAD_HOSTS = {
    "mp4upload.com": "Mp4upload",
    "filelions.top": "Vidhide",
    "movearnpre.com": "Vidhide",
    "vidhide.com": "Vidhide",
    "uqload.is": "Uqload",
    "uqload.vc": "Uqload",
    "uqload.to": "Uqload",
    "bysesukior.com": "Filemoon",
    "dhcplay.com": "Streamwish",
    "streamwish.to": "Streamwish",
}


class AnimeFLVScraper(BaseScraper):
    BASE_URL = os.environ.get("ANIMEFLV_BASE_URL", "https://vww.animeflv.one").rstrip("/")
    SOURCE_NAME = "animeflv"
    SERIE_URL_TEMPLATE = "{base}/anime/{slug}"
    TIMEOUT = 60

    # Orden de desempate dentro de cada grupo (resueltos / no resueltos). El
    # orden real de entrega lo decide el flag `resolved`: los que entregan video
    # van primero. Mp4upload entrega mp4 directo y Vidhide/Uqload un manifest
    # HLS; Filemoon y Streamwish suelen quedar como landing sin resolver.
    SERVER_PRIORITY = [
        "Mp4upload",
        "Vidhide",
        "Uqload",
        "Filemoon",
        "Streamwish",
    ]

    # Techo defensivo del paginado del directorio (el sitio tiene cientos de
    # paginas y `get_all_series` no se usa en el camino critico).
    MAX_DIRECTORY_PAGES = 50

    REFERER_MAP = {
        "Mp4upload": "https://www.mp4upload.com/",
        "Vidhide": "https://filelions.top/",
        "Uqload": "https://uqload.is/",
        "Filemoon": "https://bysesukior.com/",
        "Streamwish": "https://dhcplay.com/",
    }

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )

    # Sesion compartida a nivel de proceso, mismo motivo que en el resto de los
    # scrapers: reutilizarla evita pagar el handshake en cada llamada.
    _session_lock = threading.Lock()
    _session = None

    def _get_scraper(self):
        return shared_scraper_session(AnimeFLVScraper)

    # ------------------------------------------------------------------
    #  API BaseScraper
    # ------------------------------------------------------------------

    def get_all_series(self) -> list[dict]:
        """Recorre el directorio paginado y devuelve las series encontradas.

        El listado `/animes` mezcla capitulos recientes (`/ver/...`) con series
        (`/anime/...`); solo interesan las segundas. Se corta cuando una pagina
        no aporta slugs nuevos, cuando no hay pagina siguiente o al llegar a un
        techo defensivo.
        """
        scraper = self._get_scraper()
        series = {}
        page = 1
        max_pages = max(1, int(self.MAX_DIRECTORY_PAGES))

        while page <= max_pages:
            url = f"{self.BASE_URL}/animes?pag={page}"
            try:
                resp = scraper.get(url, timeout=self.TIMEOUT, allow_redirects=True)
                if resp.status_code != 200:
                    break
                soup = BeautifulSoup(resp.text, "html.parser")
            except Exception as e:
                logger.warning(f"Error en pagina {page} del directorio AnimeFLV: {e}")
                break

            nuevos = 0
            for a in soup.select("a[href*='/anime/']"):
                href = a.get("href", "")
                match = re.search(r"/anime/([^/\s?#]+)", href)
                if not match:
                    continue
                slug = match.group(1)
                if slug in series:
                    continue

                # El texto del enlace puede ser un badge ("OVA", "Anime"); en
                # ese caso la misma tarjeta tiene otro enlace con el titulo
                # real, que es el que interesa.
                nombre = a.get_text(" ", strip=True)
                if nombre in ("OVA", "Anime", "Pelicula", "Película", "Especial"):
                    continue
                if not nombre:
                    nombre = slug.replace("-", " ").title()

                cover_url = None
                img = a.find("img")
                if img:
                    cover_url = img.get("data-src") or img.get("src")
                    if cover_url and "cdn/img/anime.png" in cover_url:
                        cover_url = None

                series[slug] = {
                    "slug": slug,
                    "nombre": nombre,
                    "url": self.SERIE_URL_TEMPLATE.format(base=self.BASE_URL, slug=slug),
                    "cover_url": cover_url,
                }
                nuevos += 1

            if not nuevos:
                break
            if not soup.select_one("a[href*='pag=%d']" % (page + 1)):
                break
            page += 1

        return list(series.values())

    def get_series_info(self, url: str) -> dict | None:
        """Obtiene info de una serie a partir de su URL `/anime/<slug>` o `/ver/...`."""
        slug = self._series_slug_from_url(url)
        if not slug:
            return None

        scraper = self._get_scraper()
        full_url = self.SERIE_URL_TEMPLATE.format(base=self.BASE_URL, slug=slug)
        try:
            resp = scraper.get(full_url, timeout=self.TIMEOUT, allow_redirects=True)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            nombre = ""
            h2 = soup.select_one("div.info-l h2 i") or soup.select_one("h2 i")
            if h2:
                nombre = h2.get_text(" ", strip=True)
            if not nombre:
                title = soup.find("title")
                if title:
                    nombre = re.split(r"[|—]", title.get_text(strip=True))[0].strip()
            if not nombre:
                nombre = slug.replace("-", " ").title()

            return {
                "slug": slug,
                "nombre": nombre,
                "cover_url": self._cover_url(slug, soup),
                "estado": self._extract_estado(soup),
                "es_pelicula": False,
                "dia_emision": None,
            }
        except Exception as e:
            logger.error(f"Error obteniendo info de serie {full_url}: {e}")
            return None

    def get_episodes(self, slug: str) -> list[dict]:
        """Obtiene los episodios desde el JS `var eps` de la pagina de la serie."""
        scraper = self._get_scraper()
        full_url = self.SERIE_URL_TEMPLATE.format(base=self.BASE_URL, slug=slug)
        try:
            resp = scraper.get(full_url, timeout=self.TIMEOUT, allow_redirects=True)
            resp.raise_for_status()

            match = re.search(r"var\s+eps\s*=\s*(\[.*?\])\s*;", resp.text, re.S)
            if not match:
                logger.warning(f"No se encontro `var eps` para {slug}")
                return []

            rows = json.loads(match.group(1))
            episodes = []
            seen = set()
            for row in rows:
                if not isinstance(row, (list, tuple)) or not row:
                    continue
                # `_e = epn[0]` es el numero de episodio; `_cod = epn[2]` el
                # codigo opcional que algunos episodios agregan a la URL.
                try:
                    numero = int(str(row[0]).strip())
                except (TypeError, ValueError):
                    continue
                if numero in seen:
                    continue
                seen.add(numero)

                codigo = str(row[2]).strip() if len(row) > 2 and row[2] else ""
                episode_url = f"{self.BASE_URL}/ver/{slug}-{numero}"
                if codigo:
                    episode_url += f"-{codigo}"
                episodes.append({
                    "numero": numero,
                    "url": episode_url,
                    "timestamp": "",
                })

            episodes.sort(key=lambda ep: ep["numero"])
            return episodes
        except Exception as e:
            logger.error(f"Error obteniendo episodios para {slug}: {e}")
            return []

    def get_download_urls(self, episode_url: str) -> list[dict]:
        """Obtiene las descargas desde `div.dwn[data-dwn]` del episodio."""
        scraper = self._get_scraper()
        try:
            resp = scraper.get(episode_url, timeout=self.TIMEOUT, allow_redirects=True)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            raw_urls = []
            dwn = soup.select_one("div.dwn[data-dwn]")
            if dwn:
                try:
                    parsed = json.loads(dwn.get("data-dwn") or "[]")
                except (TypeError, ValueError):
                    parsed = []
                if isinstance(parsed, list):
                    raw_urls = [u for u in parsed if isinstance(u, str)]

            results = []
            seen = set()
            for raw in raw_urls:
                link = raw.strip()
                if not link or link in seen:
                    continue
                seen.add(link)

                link = self._normalize_download_url(link)
                server = self._server_name_from_url(link)
                video_url = resolve_video_url(scraper, server, link)
                results.append({
                    "server": server,
                    "url": video_url or link,
                    "size": "Desconocido",
                    "resolved": bool(video_url),
                })

            priority = {name: i for i, name in enumerate(self.SERVER_PRIORITY)}
            results.sort(key=lambda item: (
                not item.get("resolved", False),
                priority.get(item["server"], len(self.SERVER_PRIORITY)),
            ))
            return results
        except Exception as e:
            logger.error(f"Error obteniendo URLs de descarga para {episode_url}: {e}")
            return []

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    def _series_slug_from_url(self, url: str) -> str | None:
        """Resuelve el slug de la serie desde una URL de serie o de episodio."""
        match = re.search(r"animeflv\.[a-z]+/anime/([^/\s?#]+)", url or "", re.IGNORECASE)
        if match:
            return match.group(1)

        # /ver/<slug>-<numero>[-<codigo>]: el slug no se puede separar del
        # numero sin ambiguedad, asi que se lee del breadcrumb del episodio.
        if re.search(r"/ver/[^/\s?#]+", url or ""):
            return self._slug_from_episode_page(url)
        return None

    def _slug_from_episode_page(self, url: str) -> str | None:
        """Lee el slug desde el breadcrumb canonico de una pagina `/ver/`."""
        scraper = self._get_scraper()
        try:
            resp = scraper.get(url, timeout=self.TIMEOUT, allow_redirects=True)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            # El breadcrumb (`nav.nav`) es el unico enlace canonico a la serie;
            # el resto de `/anime/` en la pagina son recomendaciones.
            for a in soup.select("nav.nav a[href*='/anime/']"):
                match = re.search(r"/anime/([^/\s?#]+)", a.get("href", ""))
                if match:
                    return match.group(1)
        except Exception as e:
            logger.warning(f"No se pudo resolver el slug de la serie desde {url}: {e}")
        return None

    def _cover_url(self, slug: str, soup) -> str | None:
        """Portada de la serie: og:image, la imagen del bloque de info o el CDN."""
        meta = soup.find("meta", property="og:image")
        if meta and meta.get("content"):
            return meta["content"]
        img = soup.select_one("div.info-l img")
        if img:
            src = img.get("data-src") or img.get("src")
            if src and "cdn/img/anime.png" not in src and "cdn/img/episode.png" not in src:
                return src
        return f"{self.BASE_URL}/cdn/img/anime/{slug}.webp"

    def _extract_estado(self, soup) -> str:
        """Traduce el badge de estado de AnimeFLV al vocabulario de la app."""
        badge = soup.select_one("div.info-l .st")
        if badge:
            classes = " ".join(badge.get("class", []))
            if "c-f" in classes:
                return "concluido"
            if "c-e" in classes or "c-o" in classes or "c-p" in classes:
                return "en_emision"
            text = badge.get_text(" ", strip=True).lower()
            if "finaliz" in text:
                return "concluido"
            if "emision" in text or "emisión" in text:
                return "en_emision"
        return "desconocido"

    def _normalize_download_url(self, link: str) -> str:
        """Reescribe el link de descarga a la forma que el resolver entiende.

        - Mp4upload publica un link corto (`/<id>`) que no trae la
          configuracion del player; su resolver trabaja sobre
          `/embed-<id>.html`.
        - `movearnpre.com/file/<id>` es un espejo de Vidhide que hoy no
          resuelve DNS; `filelions.top/v/<id>` sirve el mismo archivo con el
          mismo id.
        """
        try:
            parsed = urlsplit(link)
        except ValueError:
            return link
        host = (parsed.hostname or "").lower()
        path = parsed.path.strip("/")

        if host.endswith("mp4upload.com"):
            match = re.search(r"(?:embed-)?([A-Za-z0-9]+)(?:\.html)?$", path)
            if match:
                return f"https://www.mp4upload.com/embed-{match.group(1)}.html"

        if host.endswith("movearnpre.com"):
            vid = path.split("/")[-1]
            if vid:
                return f"https://filelions.top/v/{vid}"

        return link

    def _server_name_from_url(self, url: str) -> str:
        """Deduce el servidor canonico a partir del host de la URL de descarga.

        El match es por sufijo de host (dominio o subdominio), nunca por
        subcadena. Si el host no es conocido se usa su segundo nivel como
        etiqueta, para no entregar "Desconocido" cuando el sitio suma un host.
        """
        try:
            host = (urlsplit(url).hostname or "").lower().rstrip(".")
        except ValueError:
            return "Desconocido"
        if not host:
            return "Desconocido"

        for domain in sorted(_DOWNLOAD_HOSTS, key=len, reverse=True):
            if host == domain or host.endswith("." + domain):
                return _DOWNLOAD_HOSTS[domain]

        parts = host.split(".")
        if len(parts) >= 2:
            return parts[-2].capitalize()
        return "Desconocido"


# Registrar el scraper
register_scraper("animeflv", AnimeFLVScraper)
