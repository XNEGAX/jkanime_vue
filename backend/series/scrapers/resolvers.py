"""
Resolvedores de servidores de video — compartidos entre scrapers.

Cada función recibe (scraper_instance, url) y retorna la URL directa del .mp4
o None si no pudo resolverla.
"""
import re
import logging
from html import unescape
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

TIMEOUT = 60


# Alfabeto usado por el empaquetador "dean-edwards" para los indices base-N.
DIGITS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _to_base(n, b):
    """Convierte `n` a base `b` usando el alfabeto del packer."""
    if n == 0:
        return "0"
    out = ""
    while n:
        out = DIGITS[n % b] + out
        n //= b
    return out


def _unpack_packer(payload, base, count, words):
    """Reemplaza cada indice base-N del payload por su palabra del diccionario.

    El packer reemplaza en orden descendente: los indices altos pueden contener
    a los bajos, por eso se itera de `count - 1` hacia abajo.
    """
    for i in range(count - 1, -1, -1):
        if i < len(words) and words[i]:
            payload = re.sub(r"\b" + re.escape(_to_base(i, base)) + r"\b", words[i], payload)
    return payload


def _extract_packed(js):
    """Extrae y des-empaqueta el script ofuscado `eval(function(p,a,c,k,e,d)...)()`.

    Retorna el JS decodificado o None si la pagina no trae un bloque empaquetado.
    """
    marker = "return p}('"
    idx = js.find(marker)
    if idx == -1:
        return None
    rest = js[idx + len(marker):]
    buf, i = [], 0
    while i < len(rest):
        ch = rest[i]
        if ch == "\\":
            buf.append(rest[i:i + 2]); i += 2; continue
        if ch == "'":
            break
        buf.append(ch); i += 1
    payload = "".join(buf)
    tail = rest[i + 1:]
    m = re.match(r",(\d+),(\d+),'(.*?)'\.split\('\|'\)", tail, re.S)
    if not m:
        return None
    base, count, words = int(m.group(1)), int(m.group(2)), m.group(3).split("|")
    return _unpack_packer(payload, base, count, words)


def _normalizar_embed_streamhg(url):
    """Normaliza una URL de flaswish a su pagina embed `/e/<id>`.

    Acepta `/f/<id>`, `/f/<id>_n` y `/e/<id>`. La pagina `/f/` esta protegida
    por reCAPTCHA (no automatizable), la `/e/` no. Retorna None si no hay id.
    """
    parsed = urlparse(url)
    match = re.search(r"/([fe])/([^/?#]+)", parsed.path)
    if not match:
        return None
    vid = match.group(2)
    if vid.endswith("_n"):
        vid = vid[:-2]
    if not vid:
        return None
    return f"https://{parsed.netloc}/e/{vid}"


def _parse_links_object(decoded):
    """Extrae el objeto `links={...}` del JS decodificado a un dict."""
    m = re.search(r"links\s*=\s*\{", decoded)
    if not m:
        return {}
    start = m.end() - 1
    depth, i = 0, start
    while i < len(decoded):
        if decoded[i] == "{":
            depth += 1
        elif decoded[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    block = decoded[start:i + 1]
    return {k: v for k, v in re.findall(r'"([a-zA-Z0-9_]+)"\s*:\s*"([^"]*)"', block)}


def resolve_streamhg(scraper, url):
    """Resuelve el manifest HLS de un servidor StreamHG (host flaswish.com)."""
    try:
        embed_url = _normalizar_embed_streamhg(url)
        if not embed_url:
            logger.warning(f"Streamhg resolve falló: no se pudo normalizar {url[:60]}")
            return None

        origin = "https://" + urlparse(embed_url).netloc
        resp = scraper.get(
            embed_url,
            timeout=TIMEOUT,
            allow_redirects=True,
            headers={"Referer": url or f"{origin}/"},
        )
        resp.raise_for_status()

        decoded = _extract_packed(resp.text) or resp.text
        links = _parse_links_object(decoded)

        # El reproductor elige `links.hls4 || links.hls3 || links.hls2`, pero el
        # proxy `hls4` vive en el mismo host del embed e INYECTA un segmento de
        # anuncio que el demuxer HLS de ffmpeg rechaza ("not in
        # allowed_segment_extensions"), rompiendo la descarga. El CDN externo
        # (`hls2`) descarga bien. Por eso se prefiere el candidato `.m3u8`
        # alojado en OTRO host, y el del mismo host queda de respaldo.
        embed_netloc = urlparse(embed_url).netloc
        externo = proxy = fallback_txt = None
        for key in ("hls2", "hls4", "hls3"):
            cand = links.get(key)
            if not cand:
                continue
            resolved = urljoin(f"{origin}/", cand)
            low = resolved.lower()
            if ".m3u8" in low:
                if urlparse(resolved).netloc != embed_netloc:
                    externo = externo or resolved
                else:
                    proxy = proxy or resolved
            elif fallback_txt is None and ".txt" in low:
                fallback_txt = resolved

        if externo:
            return externo
        if proxy:
            return proxy

        # Fallback: buscar el manifest directo en todo el JS decodificado.
        m = re.search(r'https?://[^"\'\s]+\.m3u8[^"\'\s]*', decoded)
        if m:
            return m.group(0)
        if fallback_txt:
            return fallback_txt
        m = re.search(r'https?://[^"\'\s]+\.txt[^"\'\s]*', decoded)
        if m:
            return m.group(0)
    except Exception as e:
        logger.warning(f"Streamhg resolve falló: {e}")
    return None


def resolve_okru(scraper, url):
    """Resuelve el video de un embed ok.ru (`/videoembed/<id>`).

    ok.ru NO publica el link en claro: lo guarda dentro del atributo
    `data-options` de `data-module="OKVideo"` como JSON con la clave
    `flashvars` -> `metadata` -> `videos` (HTML-escaped), mas un
    `hlsManifestUrl`.

    El `hlsManifestUrl` comparte host con el embed y el downloader lo trata
    como `.m3u8` -> ffmpeg, pero ese manifest responde 400 (requiere un token
    de sesion que no viene en el HTML). En cambio, las entradas de `videos`
    son MP4 directos firmados por `expires`+`sig` y responden 200
    `video/mp4` con header `ftyp` valido. Por eso se prefiere el MP4 y el
    HLS queda de respaldo.

    El orden `hd` -> `sd` -> `low` -> `lowest` sale de `type`, que es el indice
    de calidad del reproductor (0 = lowest, 1 = low, 2 = sd, 3 = hd). `mobile`
    es `type=4` y NO es una calidad: es la variante adaptativa de baja
    resolucion para datos moviles, asi que se descarta a proposito en vez de
    competir con las calidades reales. El HTML las trae en orden arbitrario.
    Se descartan tambien las marcadas `disallowed: true`.

    Retorna la URL directa o None si el embed cambio de forma.
    """
    try:
        resp = scraper.get(url, timeout=TIMEOUT, allow_redirects=True)
        resp.raise_for_status()

        # ok.ru embebe TODO el objeto del reproductor en el atributo
        # `data-options` de `data-module="OKVideo"`, con las comillas escapadas
        # como HTML (&quot;). Sin `unescape` los patrones de abajo buscan
        # comillas literales dentro de un blob que solo trae `&quot;` y no
        # matchean NADA: el resolver devuelve None aunque el link este ahi.
        blob = unescape(resp.text)

        # `videos` es una lista de objetos {name, url, type, disallowed}. Cada
        # objeto puede venir HTML-escaped dentro de data-options, asi que se
        # busca tanto crudo como escapado.
        candidates = []  # (calidad, url)
        for raw in re.finditer(
            r'\{[^{}]*?"name"\s*:\s*"(?P<name>[a-zA-Z0-9_]+)"[^{}]*?'
            r'"url"\s*:\s*"(?P<url>https?://[^"]+)"[^{}]*?\}',
            blob,
        ):
            name = raw.group("name")
            src = raw.group("url").replace("\\/", "/").replace("\\u0026", "&")
            snippet = raw.group(0)
            # Descartar entradas disallowed: el servidor las sirve con contenido
            # de error, no con video.
            if '"disallowed"\s*:\s*true' in snippet:
                continue
            # Los HLS/manifests no son un link descargable: el downloader los
            # pasaria a ffmpeg y ok.ru responde 400 por el token de sesion.
            if "m3u8" in src.lower():
                continue
            # `type` es el indice de calidad del reproductor (0=lowest .. 3=hd).
            # `mobile` (type=4) es la variante adaptativa de datos moviles, no
            # una calidad: se descarta para no degradar la descarga.
            type_match = re.search(r'"type"\s*:\s*(\d+)', snippet)
            if type_match:
                quality = int(type_match.group(1))
                if name.lower() == "mobile" or quality > 3:
                    continue
            else:
                # Sin `type`, el `name` es el unico indicador de calidad.
                quality = _OKRU_NAME_RANK.get(name.lower(), 0)
            candidates.append((quality, src))

        if candidates:
            candidates.sort(key=lambda c: c[0], reverse=True)  # hd primero
            return candidates[0][1]

        # Respaldo: manifest HLS firmado (puede responder 400, pero conserva
        # la semantica de "ultimo recurso" del resto de los resolvers).
        m = re.search(r'"hlsManifestUrl"\s*:\s*"(https?://[^"]+)"', blob)
        if m:
            return m.group(1).replace("\\/", "/").replace("\\u0026", "&")
    except Exception as e:
        logger.warning(f"Ok.ru resolve falló: {e}")
    return None


# Orden de calidad de respaldo cuando el objeto de `videos` no trae `type`.
# Los valores replican el indice de calidad del reproductor (0=lowest .. 3=hd);
# `mobile` queda fuera: degrada a baja resolucion y nunca debe ganar.
_OKRU_NAME_RANK = {"hd": 3, "sd": 2, "low": 1, "lowest": 0}


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


def _absolute_url(base: str, candidate: str) -> str:
    """Normaliza un candidato del JS empaquetado a una URL absoluta.

    El packer escapa las barras como `\\/`, y algunos players publican el
    manifest como protocolo relativo (`//cdn...`). `urljoin` resuelve el resto.
    """
    candidate = candidate.replace("\\/", "/").replace("\\u0026", "&").strip()
    if candidate.startswith("//"):
        return "https:" + candidate
    if candidate.startswith("http"):
        return candidate
    return urljoin(base, candidate)


def resolve_packed_links(scraper, url):
    """Resuelve embeds que esconden el manifest dentro de JS empaquetado.

    Vidhide (filelions/movearnpre) y Uqload entregan la pagina como
    `eval(function(p,a,c,k,e,d)...)()` con el video adentro. Se des-empaqueta y
    se busca, en orden:
      1. el objeto `links={...}` con las claves `hls2`/`hls3`/`hls4`,
      2. un `sources: [{file: "..."}]` de jwplayer,
      3. un `file: "..."` que apunte a `.m3u8`/`.mp4`,
      4. cualquier `.m3u8`/`.mp4` absoluto en el JS o en el HTML crudo.

    No sirve para Filemoon (SPA que arma el player en el cliente) ni para
    Streamwish (interstitial con JS propio): esos devuelven None y el caller
    los entrega como `resolved: False`.
    """
    try:
        resp = scraper.get(
            url,
            timeout=TIMEOUT,
            allow_redirects=True,
            headers={"Referer": url},
        )
        resp.raise_for_status()

        decoded = _extract_packed(resp.text) or resp.text

        links = _parse_links_object(decoded)
        for key in ("hls2", "hls3", "hls4"):
            candidate = links.get(key)
            if candidate:
                return _absolute_url(url, candidate)

        # jwplayer / video.js: sources = [{file: "..."}]
        match = re.search(
            r'sources\s*:\s*\[[^\]]*?file\s*:\s*["\']([^"\']+)["\']',
            decoded,
            re.S,
        )
        if match:
            return _absolute_url(url, match.group(1))

        # `file: "..."` suelto, solo si apunta a un media.
        for match in re.finditer(r'file\s*:\s*["\']([^"\']+)["\']', decoded):
            candidate = _absolute_url(url, match.group(1))
            low = candidate.lower()
            if ".m3u8" in low or ".mp4" in low:
                return candidate

        # Ultimo recurso: cualquier media absoluta en el JS o en el HTML.
        for text in (decoded, resp.text):
            match = re.search(r'https?://[^"\'\s<>]+\.(?:m3u8|mp4)[^"\'\s<>]*', text)
            if match:
                return match.group(0)
    except Exception as e:
        logger.warning(f"Packed links resolve falló para {url[:60]}: {e}")
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
    "Streamwish": resolve_streamhg,
    "Streamhg": resolve_streamhg,
    "Flaswish": resolve_streamhg,
    "Vidhide": resolve_packed_links,
    "Uqload": resolve_packed_links,
    "Ok": resolve_okru,
}


# Hosts cuyo link en latanime es una pagina de aterrizaje/embed SIN un resolver
# barato y confiable. Se declaran aca de forma explicita para que su ausencia en
# RESOLVER_MAP sea una decision documentada y no un olvido: `resolve_video_url`
# devuelve None para ellos, y el caller DEBE tratar su URL como no resuelta
# (`resolved: False`), nunca como un link de descarga listo para usar.
#
# - Savefiles / 1cloudfile: el boton de descarga exige POST/JS, no un GET simple.
# - Gofile: el link real vive detras de su API con token de invitado.
# - Mega / Mega Stream: el archivo va cifrado en el cliente; el HTML no trae mp4.
# - Byse / Hexload: embeds sin endpoint directo estable.
#
# No se agregan hacks de scraping fragiles a proposito: si en el futuro aparece
# un resolver confiable, se suma su funcion a RESOLVER_MAP y se saca el nombre
# de esta lista.
UNSUPPORTED_SERVERS = frozenset({
    "Savefiles", "Gofile", "1cloudfile", "Mega", "Mega Stream", "Byse", "Hexload",
})


def resolve_video_url(scraper, server_name: str, remote_url: str) -> str | None:
    """Resuelve la URL directa del video según el servidor."""
    resolver = RESOLVER_MAP.get(server_name)
    if resolver:
        return resolver(scraper, remote_url)
    return None
