"""
Scraper para Latanime.org — implementa BaseScraper.

Estructura del sitio:
  - Homepage:  https://latanime.org
  - Directorio: https://latanime.org/animes  (paginated)
  - Serie:     https://latanime.org/anime/<slug>
  - Episodio:  https://latanime.org/ver/<slug-episodio>

Los servidores de descarga aparecen en dos formas:
  - Enlaces directos: <a class="direct-link" href="URL">Servidor</a>
  - Players online:   <a class="play-video" data-player="BASE64_URL">nombre</a>
"""
import re
import base64
import logging

import cloudscraper
from bs4 import BeautifulSoup

from .base import BaseScraper
from .resolvers import resolve_video_url
from . import register_scraper

logger = logging.getLogger(__name__)


class LatanimeScraper(BaseScraper):
    BASE_URL = "https://latanime.org"
    SOURCE_NAME = "latanime"
    TIMEOUT = 60

    SERVER_PRIORITY = [
        "Mega",           # 1. Mega download (direct-link)
        "Mega Stream",    # 2. Mega stream (play-video)
        "Mediafire",      # 3. Mediafire download
        "Savefiles", "Gofile", "1cloudfile",
        "Pixeldrain",
        "Mp4upload", "VOE", "Mixdrop", "Doodstream",
        "Byse", "Hexload",
        "Filemoon", "Lulu", "Listeamed",
    ]

    REFERER_MAP = {
        "Mp4upload": "https://www.mp4upload.com/",
        "Mediafire": "https://www.mediafire.com/",
        "VOE": "https://voe.sx/",
        "Doodstream": "https://doodstream.com/",
        "Filemoon": "https://filemoon.sx/",
        "Lulu": "https://luluvid.com/",
        "Mixdrop": "https://mixdrop.co/",
        "Pixeldrain": "https://pixeldrain.com/",
    }

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )

    # Resolvedores específicos de Latanime (para servidores que ya vienen resueltos)
    DIRECT_SERVERS = {"Mediafire", "Mega", "Savefiles", "Gofile", "1cloudfile", "Pixeldrain"}

    def _get_scraper(self):
        return cloudscraper.create_scraper(browser={"custom": self.USER_AGENT})

    def _extract_slug(self, url: str) -> str:
        """Extrae el slug de una URL de Latanime."""
        # /anime/<slug>  o  /ver/<slug-episodio>
        match = re.search(r'latanime\.org/(?:anime|ver)/([^/\s?#]+)', url)
        if match:
            return match.group(1)
        return ""

    # ------------------------------------------------------------------
    #  API BaseScraper
    # ------------------------------------------------------------------

    def get_all_series(self) -> list[dict]:
        """Obtiene todas las series desde el directorio paginado."""
        scraper = self._get_scraper()
        series_dict = {}
        page = 1

        while True:
            url = f"{self.BASE_URL}/animes?page={page}"
            try:
                resp = scraper.get(url, timeout=self.TIMEOUT)
                if resp.status_code != 200:
                    break
                soup = BeautifulSoup(resp.text, "html.parser")

                # Buscar cards de series del directorio
                found_any = False
                for a_tag in soup.select("a[href*='/anime/']"):
                    # Buscar el div.series dentro del enlace (estructura del directorio)
                    series_div = a_tag.find("div", class_="series")
                    if not series_div:
                        continue
                    href = a_tag["href"]
                    slug_match = re.search(r'/anime/([^/\s?#]+)', href)
                    if not slug_match:
                        continue
                    slug = slug_match.group(1)
                    if slug in series_dict:
                        continue

                    found_any = True
                    nombre = ""
                    h3 = series_div.find("h3")
                    if h3:
                        nombre = h3.get_text(strip=True)
                    if not nombre:
                        nombre = a_tag.get("title", "") or series_div.get_text(strip=True)[:80]
                    if not nombre:
                        nombre = slug.replace("-", " ").title()

                    # Cover — imagen lazy con data-src
                    cover_url = None
                    img = series_div.find("img")
                    if img:
                        src = img.get("data-src") or img.get("src", "")
                        placeholders = [
                            self.BASE_URL + "/img/capblank.png",
                            self.BASE_URL + "/img/anime.png",
                            "/img/capblank.png",
                            "/img/anime.png",
                        ]
                        if src and not any(p in src for p in placeholders):
                            cover_url = src

                    series_dict[slug] = {
                        "slug": slug,
                        "nombre": nombre,
                        "url": f"{self.BASE_URL}/anime/{slug}",
                        "cover_url": cover_url,
                    }

                if not found_any:
                    break

                # Detectar si hay página siguiente
                next_btn = soup.select_one("a[rel='next'], a:has(svg.bi-caret-right-fill), a.next")
                if not next_btn:
                    break
                page += 1

            except Exception as e:
                logger.warning(f"Error en página {page} del directorio Latanime: {e}")
                break

        return list(series_dict.values())

    def get_series_info(self, url: str) -> dict | None:
        """Obtiene info de una serie desde /anime/<slug>."""
        slug = self._extract_slug(url)
        if not slug:
            # Intentar extraer slug de una URL tipo /anime/<slug>
            match = re.search(r'/anime/([^/\s?#]+)', url)
            if match:
                slug = match.group(1)
        if not slug:
            return None

        scraper = self._get_scraper()
        full_url = f"{self.BASE_URL}/anime/{slug}"
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
                    nombre = title.get_text(strip=True).split("—")[0].strip()
            if not nombre:
                nombre = slug.replace("-", " ").title()

            # Cover — buscar meta og:image o cualquier img grande
            cover_url = None
            meta = soup.find("meta", property="og:image")
            if meta and meta.get("content"):
                cover_url = meta["content"]
            if not cover_url:
                img = soup.select_one(
                    "div.serieimgficha img, "
                    "div.serie-poster img, "
                    "div.portada img, "
                    "img.portada, "
                    "div.hero-poster img"
                )
                if img:
                    cover_url = img.get("data-src") or img.get("src", "")

            estado = self._extract_estado(soup)
            dia_emision = self._extract_dia_emision(soup)

            return {
                "slug": slug,
                "nombre": nombre,
                "cover_url": cover_url,
                "estado": estado,
                "es_pelicula": False,
                "dia_emision": dia_emision,
            }
        except Exception as e:
            logger.error(f"Error obteniendo info de serie {full_url}: {e}")
            return None

    def get_episodes(self, slug: str) -> list[dict]:
        """Obtiene episodios desde /anime/<slug>."""
        scraper = self._get_scraper()
        full_url = f"{self.BASE_URL}/anime/{slug}"
        try:
            resp = scraper.get(full_url, timeout=self.TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            episodes = []
            seen_numbers = set()

            # Buscar lista de episodios — estructura típica
            for ep_link in soup.select("a[href*='/ver/']"):
                href = ep_link.get("href", "")
                if not href.startswith(self.BASE_URL + "/ver/"):
                    continue

                # Extraer número
                num = None
                num_text = ep_link.get_text(strip=True)
                match = re.search(r'Episodio\s*(\d+)', num_text, re.IGNORECASE)
                if match:
                    num = int(match.group(1))
                else:
                    # Intentar extraer número del slug
                    slug_match = re.search(r'episodio[-\s]*(\d+)', href, re.IGNORECASE)
                    if slug_match:
                        num = int(slug_match.group(1))

                if num is None or num in seen_numbers:
                    continue
                seen_numbers.add(num)

                episodes.append({
                    "numero": num,
                    "url": href,
                    "timestamp": "",
                })

            # Ordenar por número ascendente
            episodes.sort(key=lambda x: x["numero"])
            return episodes

        except Exception as e:
            logger.error(f"Error obteniendo episodios para {slug}: {e}")
            return []

    def get_download_urls(self, episode_url: str) -> list[dict]:
        """Obtiene URLs de descarga desde /ver/<slug-episodio>."""
        scraper = self._get_scraper()
        try:
            resp = scraper.get(episode_url, timeout=self.TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            seen_urls = set()

            # --- 1. Enlaces directos de descarga (.direct-link) ---
            for a in soup.select("a.direct-link"):
                href = a.get("href", "").strip()
                if not href or href in seen_urls:
                    continue
                seen_urls.add(href)

                # Nombre del servidor desde el texto del span
                name_span = a.find("span")
                server_name = name_span.get_text(strip=True) if name_span else "Desconocido"

                # Sanitizar nombre
                server_name = server_name.strip()
                if not server_name:
                    server_name = "Desconocido"

                # Normalizar nombre (Cloud -> 1cloudfile, etc.)
                server_name = self._normalize_server_name(server_name)

                # Transformar URLs de servidores directos con API
                url = self._resolve_direct_url(server_name, href)

                results.append({
                    "server": server_name,
                    "url": url,
                    "size": "Desconocido",
                })

            # --- 2. Players online (data-player en base64) ---
            for li in soup.select("li#play-video a.play-video"):
                b64 = li.get("data-player", "")
                if not b64:
                    continue
                try:
                    decoded_url = base64.b64decode(b64).decode("utf-8")
                except Exception:
                    continue

                if decoded_url in seen_urls:
                    continue
                seen_urls.add(decoded_url)

                server_name = li.get_text(strip=True) or "Desconocido"
                server_name = server_name.strip().capitalize()

                # Mapear nombres a los estándar
                server_name = self._normalize_server_name(server_name)

                # Distinguir stream de descarga directa para Mega
                if server_name == "Mega":
                    server_name = "Mega Stream"

                # Intentar resolver la URL del video
                video_url = resolve_video_url(scraper, server_name, decoded_url)
                if video_url:
                    results.append({
                        "server": server_name,
                        "url": video_url,
                        "size": "Desconocido",
                    })
                else:
                    # Si no se pudo resolver, igual agregar la URL decodificada
                    # (algunos servers como Savefiles, Gofile ya vienen como enlace directo)
                    results.append({
                        "server": server_name,
                        "url": decoded_url,
                        "size": "Desconocido",
                    })

            # --- 3. Ordenar por prioridad ---
            priority_map = {s: i for i, s in enumerate(self.SERVER_PRIORITY)}
            results.sort(key=lambda x: priority_map.get(x["server"], len(self.SERVER_PRIORITY)))

            return results

        except Exception as e:
            logger.error(f"Error obteniendo URLs de descarga para {episode_url}: {e}")
            return []

    def _resolve_direct_url(self, server_name: str, url: str) -> str:
        """Transforma URLs de descarga directa a su endpoint de descarga real."""
        # Pixeldrain: /u/<ID> -> /api/file/<ID>
        if server_name == "Pixeldrain":
            match = re.search(r'pixeldrain\.com/u/([a-zA-Z0-9]+)', url)
            if match:
                return f"https://pixeldrain.com/api/file/{match.group(1)}"
        return url

    def _normalize_server_name(self, name: str) -> str:
        """Normaliza nombres de servidores a los estándar."""
        mapping = {
            "dsvplay": "Doodstream",
            "Byse": "Byse",
            "Hexload": "Hexload",
            "Savefiles": "Savefiles",
            "Mega": "Mega",
            "Mixdrop": "Mixdrop",
            "mxdrop": "Mixdrop",
            "Voe": "VOE",
            "Mp4upload": "Mp4upload",
            "Mediafire": "Mediafire",
            "Gofile": "Gofile",
            "1cloudfile": "1cloudfile",
            "Cloud": "1cloudfile",
            "Doodstream": "Doodstream",
            "Filemoon": "Filemoon",
            "Lulu": "Lulu",
            "Listeamed": "Listeamed",
            "Pixeldrain": "Pixeldrain",
        }
        # Case-insensitive match
        lower = name.lower().replace(" ", "")
        for key, val in mapping.items():
            if key.lower() == lower:
                return val
        return name

    def _extract_estado(self, soup) -> str:
        """Extrae estado de la serie desde el HTML."""
        try:
            text = soup.get_text()
            lower = text.lower()
            if "finalizado" in lower or "concluido" in lower or "completado" in lower:
                return "concluido"
            if "emision" in lower or "emisión" in lower or "en emision" in lower:
                return "en_emision"
        except Exception:
            pass
        return "desconocido"

    def _extract_dia_emision(self, soup):
        """Intenta extraer día de emisión."""
        DIA_MAP = {
            'lunes': 'lunes', 'martes': 'martes', 'miercoles': 'miercoles',
            'miércoles': 'miercoles', 'jueves': 'jueves', 'viernes': 'viernes',
            'sabado': 'sabado', 'sábado': 'sabado', 'domingo': 'domingo',
        }
        try:
            text = soup.get_text()
            for dia_es, dia_key in DIA_MAP.items():
                pattern = rf"(?:Pr[oó]ximo|Nuevo)\s*(?:episodio|cap[íi]tulo)?\s*:\s*{dia_es}"
                if re.search(pattern, text, re.IGNORECASE):
                    return dia_key
        except Exception:
            pass
        return None


# Registrar el scraper
register_scraper("latanime", LatanimeScraper)
