"""
Resolvedores de servidores de video — compartidos entre scrapers.

Cada función recibe (scraper_instance, url) y retorna la URL directa del .mp4
o None si no pudo resolverla.
"""
import re
import logging

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

TIMEOUT = 60


def resolve_mediafire(scraper, url):
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


def resolve_mega(scraper, url):
    try:
        resp = scraper.get(url, timeout=TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        match = re.search(r'href="([^"]+)"[^>]*id="downloadButton"', resp.text)
        if match:
            return match.group(1)
        match = re.search(r'https?://[^"\'\\s<>]*\.mp4[^"\'\\s<>]*', resp.text)
        if match:
            return match.group(0)
        if resp.url and resp.url != url:
            return resp.url
    except Exception as e:
        logger.warning(f"Mega resolve falló: {e}")
    return None


def resolve_mp4upload(scraper, url):
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


def resolve_streamtape(scraper, url):
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


def resolve_voe(scraper, url):
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


def resolve_doodstream(scraper, url):
    try:
        # Intentar con /pass_md5 en el dominio de la URL final (dsvplay.com, playmogo.com, etc.)
        resp = scraper.get(url, timeout=TIMEOUT, allow_redirects=True)
        resp.raise_for_status()

        # Buscar /pass_md5 en la respuesta
        match = re.search(r'(/pass_md5/[^"\'\\s]*)', resp.text)
        if match:
            # Usar el dominio de la URL final para construir el endpoint
            from urllib.parse import urlparse
            parsed = urlparse(resp.url)
            base_domain = f"{parsed.scheme}://{parsed.netloc}"
            pass_md5_url = f"{base_domain}{match.group(0)}"
            referer = f"{base_domain}/"
            resp2 = scraper.get(pass_md5_url, timeout=TIMEOUT, headers={"Referer": referer})
            resp2.raise_for_status()
            video_url = resp2.text.strip()
            if video_url.startswith("http"):
                return video_url

        # Fallback: buscar .mp4 en toda la pagina
        match = re.search(r'https?://[^"\'\\s<>]*\.mp4[^"\'\\s<>]*', resp.text)
        if match:
            return match.group(0)

        # Buscar .m3u8 (HLS)
        match = re.search(r'https?://[^"\'\\s<>]*\.m3u8[^"\'\\s<>]*', resp.text)
        if match:
            return match.group(0)

    except Exception as e:
        logger.warning(f"Doodstream resolve falló: {e}")
    return None


def resolve_generic_mp4(scraper, url):
    """Busca URLs de video en la pagina con multiples patrones."""
    try:
        resp = scraper.get(url, timeout=TIMEOUT, allow_redirects=True)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        text = resp.text

        # 1. Buscar .mp4 directos en el HTML
        match = re.search(r'https?://[^"\'\\s<>]*\.mp4[^"\'\\s<>]*', text)
        if match:
            return match.group(0)

        # 2. Buscar .m3u8 (HLS)
        match = re.search(r'https?://[^"\'\\s<>]*\.m3u8[^"\'\\s<>]*', text)
        if match:
            return match.group(0)

        # 3. Buscar en scripts configuraciones de video-js / jwplayer
        for script in soup.find_all("script"):
            if not script.string:
                continue
            s = script.string

            # file:/src:/url en configuraciones JS
            for pat in [
                r'["\'](?:file|src|url|source)["\']\s*[:=]\s*["\']([^"\']+\.(?:mp4|m3u8)[^"\']*)["\']',
                r'["\'](?:file|src|url|source)["\']\s*[:=]\s*["\'](https?://[^"\']+)["\']',
                r'(?:file|src)\s*:\s*["\']([^"\']+)["\']',
            ]:
                matches = re.findall(pat, s, re.IGNORECASE)
                for m in matches:
                    url_candidate = m
                    if url_candidate.startswith("//"):
                        url_candidate = "https:" + url_candidate
                    if url_candidate.startswith("http"):
                        return url_candidate

        # 4. Buscar en atributos data-* de elementos
        for tag in soup.find_all(attrs={"data-src": True, "data-url": True, "data-file": True}):
            for attr in ("data-src", "data-url", "data-file"):
                val = tag.get(attr, "")
                if val.startswith("http") and (".mp4" in val or ".m3u8" in val):
                    return val

        # 5. Buscar en <video> <source>
        for video in soup.find_all("video"):
            src = video.get("src", "")
            if src and src.startswith("http"):
                return src
            for source in video.find_all("source"):
                src = source.get("src", "")
                if src and src.startswith("http"):
                    return src

        # 6. Buscar en iframes (intentar resolver recursive)
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src", "")
            if src and (".mp4" in src or ".m3u8" in src):
                return src
            # Si el iframe apunta al mismo dominio, intentar resolverlo
            if src and src.startswith("http"):
                try:
                    resp2 = scraper.get(src, timeout=TIMEOUT)
                    resp2.raise_for_status()
                    match = re.search(r'https?://[^"\'\\s<>]*\.mp4[^"\'\\s<>]*', resp2.text)
                    if match:
                        return match.group(0)
                except Exception:
                    pass

    except Exception as e:
        logger.warning(f"Generic MP4 resolve falló para {url[:60]}: {e}")
    return None


# Mapa de resolvedores: nombre -> función
RESOLVER_MAP = {
    "Mediafire": resolve_mediafire,
    "Mega": resolve_mega,
    "Mp4upload": resolve_mp4upload,
    "Streamtape": resolve_streamtape,
    "VOE": resolve_voe,
    "Doodstream": resolve_doodstream,
    "Filemoon": resolve_generic_mp4,
    "Mixdrop": resolve_generic_mp4,
    "Lulu": resolve_generic_mp4,
    "Listeamed": resolve_generic_mp4,
    "Streamwish": resolve_generic_mp4,
    "Vidhide": resolve_generic_mp4,
}


def resolve_video_url(scraper, server_name: str, remote_url: str) -> str | None:
    """Resuelve la URL directa del video según el servidor."""
    resolver = RESOLVER_MAP.get(server_name)
    if resolver:
        return resolver(scraper, remote_url)
    return None
