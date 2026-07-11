"""
Scraper para JKanime - Adaptado del proyecto anime_downloader.
Maneja la detección de series, episodios y URLs de descarga.
"""
import re
import json
import base64
import logging
import cloudscraper
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://jkanime.net"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)
TIMEOUT = 60

SERVER_PRIORITY = [
    "Mp4upload", "Mediafire", "Streamtape", "VOE",
    "Doodstream", "Filemoon", "Mixdrop", "Streamwish", "Vidhide",
]

REFERER_MAP = {
    "Mp4upload": "https://www.mp4upload.com/",
    "Streamtape": "https://streamtape.com/",
    "Mediafire": "https://www.mediafire.com/",
    "VOE": "https://voe.sx/",
}


def get_scraper():
    return cloudscraper.create_scraper(browser={"custom": USER_AGENT})


def get_all_series_from_jkanime():
    """
    Obtiene todas las series disponibles en JKanime parseando la página principal.
    Retorna lista de dicts: {slug, nombre, url, cover_url, anio}
    """
    scraper = get_scraper()
    try:
        resp = scraper.get(BASE_URL, timeout=TIMEOUT)
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
                if not href or not href.startswith(BASE_URL):
                    continue

                slug = _extract_slug(href)
                if not slug or slug in series_dict:
                    continue

                nombre = _extract_anime_name(item)
                if not nombre:
                    nombre = slug.replace("-", " ").title()

                cover_url = _get_cover_url(scraper, slug, href)

                series_dict[slug] = {
                    "slug": slug,
                    "nombre": nombre,
                    "url": f"{BASE_URL}/{slug}/",
                    "cover_url": cover_url,
                }

        return list(series_dict.values())

    except Exception as e:
        logger.error(f"Error obteniendo series de JKanime: {e}")
        return []


def _is_pelicula(soup):
    """Detecta si el contenido es una película (vs serie/anime)."""
    tipo_tag = soup.find("li", attrs={"rel": "tipo"})
    if tipo_tag:
        text = tipo_tag.get_text(strip=True).lower()
        if "pelicula" in text:
            return True
    return False


def get_episodes_for_series(slug):
    """
    Obtiene todos los episodios disponibles para una serie usando AJAX pagination.
    Para películas, usa /pelicula/ en vez de /{numero}/.
    Retorna lista de dicts: {numero, url}
    """
    scraper = get_scraper()
    profile_url = f"{BASE_URL}/{slug}/"
    try:
        resp = scraper.get(profile_url, timeout=TIMEOUT)
        resp.raise_for_status()

        from bs4 import BeautifulSoup as _BS
        soup = _BS(resp.text, "html.parser")
        es_pelicula = _is_pelicula(soup)

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
                ajax_url = f"{BASE_URL}/ajax/episodes/{anime_id}/{page}"
                headers = {
                    "X-CSRF-TOKEN": csrf_token,
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": profile_url,
                }
                ajax_resp = scraper.post(
                    ajax_url,
                    data={"_token": csrf_token},
                    headers=headers,
                    timeout=TIMEOUT,
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
                        ep_url = f"{BASE_URL}/{slug}/pelicula/"
                    else:
                        ep_url = f"{BASE_URL}/{slug}/{ep_num}/"
                    ep_timestamp = ep.get("timestamp", "")
                    episodes.append({
                        "numero": int(ep_num),
                        "url": ep_url,
                        "timestamp": ep_timestamp,
                    })

                total = data.get("total", 0)
                pagination_conf = 16
                total_pages = (total + pagination_conf - 1) // pagination_conf
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


def check_episode_exists(slug, episode_number):
    """
    Verifica si un episodio específico existe en JKanime.
    Retorna la URL si existe, None si no.
    """
    scraper = get_scraper()
    url = f"{BASE_URL}/{slug}/{episode_number}/"
    try:
        resp = scraper.get(url, timeout=TIMEOUT)
        if resp.status_code == 200 and "Episodio" in resp.text:
            return url
        return None
    except Exception:
        return None


def get_download_urls(episode_url):
    """
    Obtiene las URLs de descarga disponibles para un episodio.
    Retorna lista de dicts: {server, url, size}
    """
    scraper = get_scraper()
    try:
        resp = scraper.get(episode_url, timeout=TIMEOUT)
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

        return results

    except Exception as e:
        logger.error(f"Error obteniendo URLs de descarga para {episode_url}: {e}")
        return []


def resolve_video_url(scraper, server_name, remote_url):
    """Resuelve la URL directa del video según el servidor."""
    resolvers = {
        "Mp4upload": _resolve_mp4upload,
        "Streamtape": _resolve_streamtape,
        "Mediafire": _resolve_mediafire,
        "VOE": _resolve_voe,
        "Doodstream": _resolve_doodstream,
        "Filemoon": _resolve_generic_mp4,
        "Mixdrop": _resolve_generic_mp4,
        "Streamwish": _resolve_generic_mp4,
        "Vidhide": _resolve_generic_mp4,
    }
    resolver = resolvers.get(server_name)
    if resolver:
        return resolver(scraper, remote_url)
    return None


def _resolve_mp4upload(scraper, url):
    try:
        resp = scraper.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        match = re.search(r'src:\s*"([^"]+\.mp4[^"]*)"', resp.text)
        if match:
            return match.group(1)
        match = re.search(r'src:\s*"([^"]+)"', resp.text)
        if match:
            src = match.group(1)
            if src.startswith("//"):
                src = "https:" + src
            return src
    except Exception as e:
        logger.warning(f"Mp4upload resolve falló: {e}")
    return None


def _resolve_streamtape(scraper, url):
    try:
        resp = scraper.get(url, timeout=TIMEOUT)
        resp.raise_for_status()

        inner_match = re.search(
            r"get_video\?id=([^\"'&\s]+)&expires=(\d+)&ip=([^\"'&\s]+)&token=([^\"'&\s]+)",
            resp.text,
        )
        if inner_match:
            return (
                f"https://streamtape.com/get_video?id={inner_match.group(1)}"
                f"&expires={inner_match.group(2)}"
                f"&ip={inner_match.group(3)}"
                f"&token={inner_match.group(4)}"
            )

    except Exception as e:
        logger.warning(f"Streamtape resolve falló: {e}")
    return None


def _resolve_mediafire(scraper, url):
    try:
        resp = scraper.get(url, timeout=TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        btn = soup.find("a", class_="input popsok")
        if btn:
            return btn.get("href", "")
        match = re.search(r'aria-label="Download file"[^>]*href="([^"]+)"', resp.text)
        if match:
            return match.group(1)
        match = re.search(r'id="downloadButton"[^>]*href="([^"]+)"', resp.text)
        if match:
            return match.group(1)
    except Exception as e:
        logger.warning(f"Mediafire resolve falló: {e}")
    return None


def _resolve_voe(scraper, url):
    try:
        resp = scraper.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        match = re.search(r'https?://[^"\'\\s<>]*\.mp4[^"\'\\s<>]*', resp.text)
        if match:
            return match.group(0)
        match = re.search(r'"file":"([^"]+\.mp4[^"]*)"', resp.text)
        if match:
            return match.group(1).replace("\\/", "/")
    except Exception as e:
        logger.warning(f"VOE resolve falló: {e}")
    return None


def _resolve_doodstream(scraper, url):
    try:
        resp = scraper.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        match = re.search(r'/pass_md5/[^"\'\\s]*', resp.text)
        if match:
            pass_md5_url = f"https://dsvplay.com{match.group(0)}"
            resp2 = scraper.get(pass_md5_url, timeout=TIMEOUT, headers={"Referer": "https://doodstream.com/"})
            resp2.raise_for_status()
            video_url = resp2.text.strip()
            if video_url.startswith("http"):
                return video_url
            return pass_md5_url
    except Exception as e:
        logger.warning(f"Doodstream resolve falló: {e}")
    return None


def _resolve_generic_mp4(scraper, url):
    try:
        resp = scraper.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        match = re.search(r'https?://[^"\'\\s<>]*\.mp4[^"\'\\s<>]*', resp.text)
        if match:
            return match.group(0)
    except Exception as e:
        logger.warning(f"Generic MP4 resolve falló: {e}")
    return None


def _extract_slug(url):
    parts = url.rstrip("/").split("/")
    if len(parts) >= 4:
        return parts[3]
    return ""


def _extract_anime_name(item):
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


def get_series_info_by_url(url):
    """
    Obtiene info de una serie desde su URL directa de JKanime.
    Retorna dict: {slug, nombre, cover_url, estado} o None si falla.
    """
    slug = _extract_slug(url)
    if not slug:
        return None

    scraper = get_scraper()
    full_url = f"{BASE_URL}/{slug}/"
    try:
        resp = scraper.get(full_url, timeout=TIMEOUT)
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

        cover_url = _get_cover_url(scraper, slug, full_url)
        estado = _extract_estado(soup)
        es_pelicula = _is_pelicula(soup)

        return {
            "slug": slug,
            "nombre": nombre,
            "cover_url": cover_url,
            "estado": estado,
            "es_pelicula": es_pelicula,
        }
    except Exception as e:
        logger.error(f"Error obteniendo info de serie {full_url}: {e}")
        return None


def _get_cover_url(scraper, slug, episode_url):
    """Intenta obtener la URL de la portada de la serie."""
    # Primero intenta con CDN directo
    cdn_url = f"https://cdn.jkdesa.com/assets/images/animes/image/{slug}.jpg"
    try:
        head = scraper.head(cdn_url, timeout=10)
        if head.status_code == 200:
            return cdn_url
    except Exception:
        pass
    # Fallback: scrape de la página del episodio
    try:
        resp = scraper.get(episode_url, timeout=TIMEOUT)
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


def _extract_estado(soup):
    """Extrae el estado de la serie (En emision, Concluido, etc)."""
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
