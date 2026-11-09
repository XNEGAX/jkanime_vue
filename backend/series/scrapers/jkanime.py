"""
Scraper para JKanime.net — implementa BaseScraper.
"""
import re
import json
import base64
import logging
import threading

from bs4 import BeautifulSoup

from .base import BaseScraper
from .cache import SCRAPE_CACHE, TRENDING_CACHE, shared_scraper_session
from .resolvers import resolve_video_url
from . import register_scraper

logger = logging.getLogger(__name__)

# Plantilla del poster de serie en el CDN. La extension `.jpg` es OBLIGATORIA:
# el CDN no la deduce. Sin ella la URL responde 404 (un HTML de error de nginx,
# `content-type: text/html`) para todos los slugs, y como el codigo de guardado
# solo acepta HTTP 200 la serie se queda sin portada o cae al fallback del
# scraping. Vive aqui y no duplicada en `trending.py` porque eran dos copias
# escritas a mano y la de `trending.py` perdió la extension: el bug se dejo pasar
# porque las dos "funcionaban" y solo una compilaba la URL correcta.
CDN_PORTADA = "https://cdn.jkdesa.com/assets/images/animes/image/{slug}.jpg"


def _es_portada_de_la_serie(src: str, slug: str) -> bool:
    """True si `src` es el poster vertical de `slug` en el CDN.

    Anclado al path exacto del poster a proposito. Un filtro flojo
    (`slug in src and "/image/" in src`) tambien acepta las capturas de capitulo,
    porque `animes/video/image/jkvideo_*.jpg` (1280x720) contiene `/image/` y su
    hash puede coincidir con el slug; y `/image_thumb/` es la familia de la
    miniatura de capitulo. Aqui el segmento siguiente a `/animes/` tiene que ser
    exactamente `image`, y en las dos familias de capturas ese segmento es
    `video`, asi que no pueden pasar ni por accidente.

    Se ignoran query string y fragmento para no depender de que jkanime anada
    cache-busting a la URL.
    """
    ruta = src.split("?", 1)[0].split("#", 1)[0]
    return ruta.endswith(f"/animes/image/{slug}.jpg")


def _es_portada_de_la_serie_aproximada(src: str, slug: str) -> bool:
    """Como `_es_portada_de_la_serie` pero tolera que el nombre del poster
    EMPIECE con el slug en vez de ser identico.

    jkanime trunca slugs largos para la URL pero sube el poster con el nombre
    completo: la serie 450 tiene slug de 220 chars (`...hitotachi-dai`) y su
    poster es `...hitotachi-daijoubu.jpg`. Con el match exacto la portada nunca
    se encontraba y `refrescar-portada` devolvia 500. El ancla `/animes/image/`
    sigue excluyendo las capturas de capitulo (`/animes/video/...`), que es la
    proteccion que importa; por eso este fallback solo se usa cuando el match
    exacto no aparece.
    """
    ruta = src.split("?", 1)[0].split("#", 1)[0]
    marca = f"/animes/image/{slug}"
    return marca in ruta and ruta.endswith(".jpg")


class JKanimeScraper(BaseScraper):
    BASE_URL = "https://jkanime.net"
    SOURCE_NAME = "jkanime"
    TIMEOUT = 60
    EPISODES_PER_PAGE = 16

    # jkanime esta detras de un Managed Challenge de Cloudflare: sin la cookie
    # `cf_clearance` TODA peticion vuelve 403 y todos los metodos caen a su
    # `except` (lista vacia, sin descargas). Ver scrapers/cf_clearance.py.
    CF_CLEARANCE = True

    SERVER_PRIORITY = [
        "Mediafire", "Mega", "Mp4upload", "Streamtape", "VOE",
        "Doodstream", "Filemoon", "Mixdrop", "Streamwish", "Vidhide",
    ]

    REFERER_MAP = {
        "Mp4upload": "https://www.mp4upload.com/",
        "Streamtape": "https://streamtape.com/",
        "Mediafire": "https://www.mediafire.com/",
        "VOE": "https://voe.sx/",
        "Streamwish": "https://flaswish.com/",
        "Streamhg": "https://flaswish.com/",
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

    # Sesión compartida a nivel de proceso. Antes se creaba una sesión nueva en
    # cada llamada a _get_scraper(), y cada sesión nueva tiene que resolver el
    # desafío de Cloudflare desde cero: la misma URL se midió entre 1.48s y
    # 49.43s según si la sesión estaba caliente. Ver series/scrapers/cache.py.
    _session_lock = threading.Lock()
    _session = None

    def _get_scraper(self):
        return shared_scraper_session(JKanimeScraper)

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

    def get_trending(self, force=False):
        """Obtiene los ultimos episodios del trending de la pagina principal.

        Va por `TRENDING_CACHE` (30 min) y no por `SCRAPE_CACHE` (24h): el
        trending es justamente la lista que el usuario quiere ver fresca, y el
        scrape real se midio en 0.65s, asi que un TTL de 24h no ahorraba trabajo
        y si congelaba la pantalla. `force=True` lo usa la tarea horaria y el
        boton manual, que jamas pueden devolver cache. Ver `scrapers/cache.py`.
        """
        return TRENDING_CACHE.get_or_set(
            ("jkanime", "trending"),
            self._scrape_trending,
            force=force,
        )

    def _scrape_trending(self):
        """Scraping real del trending. Lo llama la cache, nunca directamente."""
        scraper = self._get_scraper()
        try:
            resp = scraper.get(self.BASE_URL, timeout=self.TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            trending = soup.find("div", class_="trending__anime")
            if not trending:
                logger.warning("No se encontro el contenedor trending__anime")
                return []

            tabs = {
                "animes": "Animes",
                "donghuas": "Donghuas",
                "ovas": "Ovas",
            }
            results = []
            for tab_id, tab_name in tabs.items():
                pane = trending.find("div", id=tab_id)
                if not pane:
                    continue
                cards = pane.find_all("div", class_="card")
                for card in cards:
                    a_tag = card.find("a")
                    if not a_tag:
                        continue
                    url = a_tag.get("href", "")
                    if not url:
                        continue

                    img = card.find("img", class_="card-img-top")
                    # La tarjeta del trending expone DOS imagenes: `src` es la
                    # captura del capitulo (1280x720, `animes/video/image/
                    # jkvideo_*.jpg`) y el poster vertical de la serie esta en
                    # `data-animepic` (`animes/image/{slug}.jpg`). Medido en el
                    # trending real: 71 de 72 tarjetas traen captura en `src` y
                    # las 72 traen el poster en `data-animepic`. Se lee
                    # `data-animepic` primero y `src` queda de respaldo para las
                    # tarjetas que no lo traigan, porque leer `src` guardaba la
                    # captura como si fuera la portada de la serie.
                    imagen = (
                        (img.get("data-animepic") or img.get("src", ""))
                        if img else ""
                    )

                    h5 = card.find("h5", class_="card-title")
                    if not h5:
                        h5 = card.find("h5", class_="strlimit")
                    nombre = h5.get_text(strip=True) if h5 else ""

                    badge = card.find("span", class_="badge-primary")
                    episodio_text = badge.get_text(strip=True) if badge else ""
                    episodio = ""
                    ep_match = re.search(r"(\d+)", episodio_text)
                    if ep_match:
                        episodio = ep_match.group(1)

                    results.append({
                        "url": url,
                        "imagen": imagen,
                        "nombre": nombre,
                        "episodio": episodio,
                        "tab": tab_name,
                    })
            return results
        except Exception as e:
            logger.error(f"Error obteniendo trending de JKanime: {e}")
            return []

    def get_series_info(self, url: str) -> dict | None:
        """Obtiene info de una serie desde su URL directa de JKanime.

        La clave de cache es el slug, no la URL: el request path arma
        `BASE_URL/<slug>/` (views) y el worker pasa `serie.url` desde la BD
        (tasks/fuente). Mismo slug, misma clave, un solo scrape.
        """
        slug = self._extract_slug(url)
        if not slug:
            return None

        return SCRAPE_CACHE.get_or_set(
            ("jkanime", "series_info", slug),
            lambda: self._scrape_series_info(slug),
        )

    def _scrape_series_info(self, slug: str) -> dict | None:
        """Scraping real de una serie. Lo llama la cache, nunca directamente."""
        scraper = self._get_scraper()
        full_url = f"{self.BASE_URL}/{slug}/"
        try:
            resp = scraper.get(full_url, timeout=self.TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            nombre = self._extract_nombre_serie(soup, slug)

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
                        "resolved": True,
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

    def _extract_nombre_serie(self, soup, slug):
        """Nombre de la serie desde la pagina de la serie.

        La pagina de serie de jkanime NO trae `<h1>`: el titulo vive en un `<h3>`
        dentro de `div.anime_info`. Antes se leia `h1` (siempre vacio) y se caia
        al `<title>`, que en jkanime es `"{nombre} - anime {nombre} online
        JkAnime"`: el nombre quedaba DUPLICADO y, si superaba los 255 chars del
        campo, truncado a la mitad (ver serie 450). El `<title>` queda como
        ultimo recurso, parseado para sacarle el sufijo.
        """
        info_div = soup.find("div", class_="anime_info")
        if info_div:
            h3 = info_div.find("h3")
            if h3:
                nombre = h3.get_text(strip=True)
                if nombre:
                    return nombre

        h1 = soup.find("h1")
        if h1:
            nombre = h1.get_text(strip=True)
            if nombre:
                return nombre

        title = soup.find("title")
        if title:
            raw = title.get_text(strip=True)
            # "Nombre - anime Nombre online JkAnime" -> "Nombre"
            raw = re.split(r"\s+-\s+anime\s+", raw, maxsplit=1)[0]
            raw = re.sub(r"\s+online\s+JkAnime\s*$", "", raw, flags=re.IGNORECASE).strip()
            if raw:
                return raw

        return slug.replace("-", " ").title()

    def _is_pelicula(self, soup):
        tipo_tag = soup.find("li", attrs={"rel": "tipo"})
        if tipo_tag:
            text = tipo_tag.get_text(strip=True).lower()
            if "pelicula" in text:
                return True
        return False

    def _get_cover_url(self, scraper, slug, episode_url):
        cdn_url = CDN_PORTADA.format(slug=slug)
        try:
            head = scraper.head(cdn_url, timeout=10)
            if head.status_code == 200:
                return cdn_url
        except Exception:
            pass
        # El CDN no siempre tiene el poster (series viejas, slug renombrado), asi
        # que queda buscarlo en el HTML. El filtro va anclado al path del poster
        # por lo que se explica en `_es_portada_de_la_serie`: antes se aceptaba
        # cualquier `src` con `/image/` y el resultado eran capturas de capitulo.
        # Se prioriza el match exacto; el aproximado solo se usa si no aparece
        # ninguno exacto (ver `_es_portada_de_la_serie_aproximada`).
        try:
            resp = scraper.get(episode_url, timeout=self.TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            aproximada = None
            for img in soup.find_all("img"):
                src = img.get("src", "")
                if _es_portada_de_la_serie(src, slug):
                    return src
                if aproximada is None and _es_portada_de_la_serie_aproximada(src, slug):
                    aproximada = src
            # `og:image` tambien pasa por el filtro: en la pagina de un EPISODIO es
            # la miniatura del capitulo (`animes/video/image_thumb/...`, 350x197),
            # y `get_all_series` scrappea paginas de episodio, no de serie. Sin
            # esto, una serie sin poster en el CDN se guardaba con esa miniatura.
            meta = soup.find("meta", property="og:image")
            if meta and meta.get("content"):
                og = meta["content"]
                if _es_portada_de_la_serie(og, slug):
                    return og
                if aproximada is None and _es_portada_de_la_serie_aproximada(og, slug):
                    aproximada = og
            if aproximada:
                return aproximada
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
