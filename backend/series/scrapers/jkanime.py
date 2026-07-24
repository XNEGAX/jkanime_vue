"""
Scraper para JKanime.net — implementa BaseScraper.
"""
import re
import json
import base64
import logging

import cloudscraper
from bs4 import BeautifulSoup

from .base import BaseScraper
from .resolvers import resolve_video_url
from . import register_scraper

logger = logging.getLogger(__name__)


class JKanimeScraper(BaseScraper):
    BASE_URL = "https://jkanime.net"
    SOURCE_NAME = "jkanime"
    TIMEOUT = 60
    EPISODES_PER_PAGE = 16

    SERVER_PRIORITY = [
        "Mediafire", "Mega", "Mp4upload", "Streamtape", "VOE",
        "Doodstream", "Filemoon", "Mixdrop", "Streamwish", "Vidhide",
    ]

    REFERER_MAP = {
        "Mp4upload": "https://www.mp4upload.com/",
        "Streamtape": "https://streamtape.com/",
        "Mediafire": "https://www.mediafire.com/",
        "VOE": "https://voe.sx/",
    }

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )

    DIA_MAP = {
        'lunes': 'lunes', 'martes': 'martes', 'miercoles': 'miercoles',
        'miércoles': 'miercoles', 'jueves': 'jueves', 'viernes': 'viernes',
        'sabado': 'sabado', 'sábado': 'sabado', 'domingo': 'domingo',
    }

    def _get_scraper(self):
        return cloudscraper.create_scraper(browser={"custom": self.USER_AGENT})

    # ------------------------------------------------------------------
    #  API BaseScraper
    # ------------------------------------------------------------------

    def get_all_series(self):
        """Obtiene todas las series desde la página principal."""
        scraper = self._get_scraper()
        try:
            resp = scraper.get(self.BASE_URL, timeout=self.TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            series_dict = {}

            tabs = {"animes": "#animes", "donghuas": "#donghuas", "ovas": "#ovas"}
            for tab_name, tab_id in tabs.items():
                pane = soup.find("div", id=tab_id.lstrip("#"))
                if not pane:
                    continue
                items = pane.find_all("div", class_="dir1")
                for item in items:
                    a_tag = item.find("a")
                    if not a_tag:
                        continue
                    href = a_tag.get("href", "")
                    if not href or not href.startswith(self.BASE_URL):
                        continue
                    slug = self._extract_slug(href)
                    if not slug or slug in series_dict:
                        continue
                    nombre = self._extract_anime_name(item)
                    if not nombre:
                        nombre = slug.replace("-", " ").title()
                    cover_url = self._get_cover_url(scraper, slug, href)
                    series_dict[slug] = {
                        "slug": slug,
                        "nombre": nombre,
                        "url": f"{self.BASE_URL}/{slug}/",
                        "cover_url": cover_url,
                    }
            return list(series_dict.values())
        except Exception as e:
            logger.error(f"Error obteniendo series de JKanime: {e}")
            return []

    def get_series_info(self, url: str) -> dict | None:
        """Obtiene info de una serie desde su URL directa de JKanime."""
        slug = self._extract_slug(url)
        if not slug:
            return None

        scraper = self._get_scraper()
        full_url = f"{self.BASE_URL}/{slug}/"
        try:
            resp = scraper.get(full_url, timeout=self.TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            nombre = ""
            h1 = soup.find("h1")
            if h1:
                nombre = h1.get_text(strip=True)
            if not nombre:
                title = soup.find("title")
                if title:
                    nombre = title.get_text(strip=True).split("|")[0].strip()
            if not nombre:
                nombre = slug.replace("-", " ").title()

            cover_url = self._get_cover_url(scraper, slug, full_url)
            estado = self._extract_estado(soup)
            es_pelicula = self._is_pelicula(soup)
            dia_emision = self._extract_dia_emision(soup)

            return {
                "slug": slug,
                "nombre": nombre,
                "cover_url": cover_url,
                "estado": estado,
                "es_pelicula": es_pelicula,
                "dia_emision": dia_emision,
            }
        except Exception as e:
            logger.error(f"Error obteniendo info de serie {full_url}: {e}")
            return None

    def get_episodes(self, slug: str) -> list[dict]:
        """Obtiene episodios vía AJAX pagination."""
        scraper = self._get_scraper()
        profile_url = f"{self.BASE_URL}/{slug}/"
        try:
            resp = scraper.get(profile_url, timeout=self.TIMEOUT)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            es_pelicula = self._is_pelicula(soup)

            csrf_token = None
            token_match = re.search(r'name="csrf-token"\s+content="([^"]+)"', resp.text)
            if token_match:
                csrf_token = token_match.group(1)

            anime_id_match = re.search(r'data-anime="(\d+)"', resp.text)
            if not anime_id_match:
                logger.warning(f"No se encontró anime ID para {slug}")
                return []
            anime_id = anime_id_match.group(1)

            episodes = []
            page = 1
            while True:
                try:
                    ajax_url = f"{self.BASE_URL}/ajax/episodes/{anime_id}/{page}"
                    headers = {
                        "X-CSRF-TOKEN": csrf_token,
                        "X-Requested-With": "XMLHttpRequest",
                        "Referer": profile_url,
                    }
                    ajax_resp = scraper.post(
                        ajax_url,
                        data={"_token": csrf_token},
                        headers=headers,
                        timeout=self.TIMEOUT,
                    )
                    if ajax_resp.status_code != 200:
                        break

                    data = ajax_resp.json()
                    ep_data = data.get("data", [])
                    if not ep_data:
                        break

                    for ep in ep_data:
                        ep_num = ep.get("number", 0)
                        if es_pelicula:
                            ep_url = f"{self.BASE_URL}/{slug}/pelicula/"
                        else:
                            ep_url = f"{self.BASE_URL}/{slug}/{ep_num}/"
                        ep_timestamp = ep.get("timestamp", "")
                        episodes.append({
                            "numero": int(ep_num),
                            "url": ep_url,
                            "timestamp": ep_timestamp,
                        })

                    total = data.get("total", 0)
                    total_pages = (total + self.EPISODES_PER_PAGE - 1) // self.EPISODES_PER_PAGE
                    if page >= total_pages:
                        break
                    page += 1

                except Exception as e:
                    logger.warning(f"Error en página {page} de episodios para {slug}: {e}")
                    break

            return episodes

        except Exception as e:
            logger.error(f"Error obteniendo episodios para {slug}: {e}")
            return []

    def get_download_urls(self, episode_url: str) -> list[dict]:
        """Obtiene URLs de descarga desde el JS inline `var servers = [...]`."""
        scraper = self._get_scraper()
        try:
            resp = scraper.get(episode_url, timeout=self.TIMEOUT)
            resp.raise_for_status()

            servers_match = re.search(r'var servers\s*=\s*(\[.*?\]);', resp.text, re.DOTALL)
            if not servers_match:
                logger.warning(f"No se encontraron servidores para {episode_url}")
                return []

            servers_data = json.loads(servers_match.group(1))
            results = []
            for s in servers_data:
                try:
                    remote_decoded = base64.b64decode(s["remote"]).decode("utf-8")
                except Exception:
                    remote_decoded = s.get("remote", "")

                name = s.get("server", "Unknown")
                video_url = resolve_video_url(scraper, name, remote_decoded)
                if video_url:
                    results.append({
                        "server": name,
                        "url": video_url,
                        "size": s.get("size", "Desconocido"),
                    })

            priority_map = {s: i for i, s in enumerate(self.SERVER_PRIORITY)}
            results.sort(key=lambda x: priority_map.get(x["server"], len(self.SERVER_PRIORITY)))
            return results

        except Exception as e:
            logger.error(f"Error obteniendo URLs de descarga para {episode_url}: {e}")
            return []

    # ------------------------------------------------------------------
    #  Helpers privados
    # ------------------------------------------------------------------

    def _extract_slug(self, url):
        parts = url.rstrip("/").split("/")
        if len(parts) >= 4:
            return parts[3]
        return ""

    def _extract_anime_name(self, item):
        h5 = item.find("h5", class_="card-title")
        if not h5:
            h5 = item.find("h5", class_="strlimit")
        if h5:
            name = h5.get_text(strip=True)
            if name:
                name = re.sub(r'\s*-\s*\d+$', '', name).strip()
                return name
        a_tag = item.find("a")
        if a_tag:
            title = a_tag.get("title", "")
            if title:
                return title
        return ""

    def _is_pelicula(self, soup):
        tipo_tag = soup.find("li", attrs={"rel": "tipo"})
        if tipo_tag:
            text = tipo_tag.get_text(strip=True).lower()
            if "pelicula" in text:
                return True
        return False

    def _get_cover_url(self, scraper, slug, episode_url):
        cdn_url = f"https://cdn.jkdesa.com/assets/images/animes/image/{slug}.jpg"
        try:
            head = scraper.head(cdn_url, timeout=10)
            if head.status_code == 200:
                return cdn_url
        except Exception:
            pass
        try:
            resp = scraper.get(episode_url, timeout=self.TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for img in soup.find_all("img"):
                src = img.get("src", "")
                if slug in src and ("/image/" in src or "/image_thumb/" in src):
                    return src
            meta = soup.find("meta", property="og:image")
            if meta and meta.get("content"):
                return meta["content"]
        except Exception:
            pass
        return None

    def _extract_estado(self, soup):
        try:
            data_div = soup.find("div", class_="anime_data")
            if data_div:
                text = data_div.get_text()
                match = re.search(r"Estado:\s*([^\n|]+)", text)
                if match:
                    raw = match.group(1).strip()
                    lower = raw.lower()
                    if "concluido" in lower or "finalizado" in lower or "completado" in lower:
                        return "concluido"
                    if "emision" in lower or "emisión" in lower or "en curso" in lower:
                        return "en_emision"
                    return raw
        except Exception:
            pass
        return "desconocido"

    def _extract_dia_emision(self, soup):
        try:
            text = soup.get_text()
            match = re.search(
                r"Pr[oó]ximo\s*episodio:\s*([A-Za-záéíóúñ]+)",
                text, re.IGNORECASE
            )
            if match:
                raw = match.group(1).strip().lower()
                dia = self.DIA_MAP.get(raw)
                if dia:
                    return dia
            match = re.search(r"Emitido:\s*([A-Za-záéíóúñ]+)", text)
            if match:
                raw = match.group(1).strip().lower()
                return self.DIA_MAP.get(raw)
        except Exception:
            pass
        return None


# Registrar el scraper
register_scraper("jkanime", JKanimeScraper)
