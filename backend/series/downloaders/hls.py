"""
HLS transport for flaswish/streamwish and hentaid.tv.

These hosts only expose an HLS manifest, so an episode has to be remuxed into
an MP4 before the shared validator (`tasks.py:_validar_mp4`) can inspect it.

The manifest is a VOD playlist of MPEG-TS segments. We download the segments
ourselves with `requests` and only ask ffmpeg to remux the LOCAL concatenation:

  * ffmpeg on Windows uses Schannel and, against these CDNs, that path is
    brutally slow (0.02-0.07 MB/s, constant `-10054` session-invalidation
    retries). Python's `requests` uses OpenSSL and runs 5-10x faster.
  * Segments can be fetched CONCURRENTLY. The CDN throttles roughly per
    connection (~0.36 MB/s), so 8 workers reach ~2.5-3.5 MB/s aggregate.
  * Once the bytes are local, the remux is trivial and fast (no network).

Encrypted (`#EXT-X-KEY`) or fragmented (`#EXT-X-MAP`, byterange) manifests fall
back to a direct ffmpeg pass, which understands them.

This module owns the toolchain boundary. ffmpeg availability is a property of
the machine, not of the episode, so it is probed once per process and reported
as `HlsToolchainError` *before* anything is spawned.
"""
import logging
import os
import re
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin

from ..ffmpeg_utils import find_ffmpeg

import requests

from ..task_runner import TaskCancelled

logger = logging.getLogger(__name__)

# UA por defecto para los segmentos/playlist, que exigen un navegador real.
# No es configurable a proposito: es el mismo que usa el scraper.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# Cuantos segmentos se bajan en paralelo. El CDN limita por conexion, asi que
# 8 workers dan ~7x sobre uno solo sin saturar la maquina.
MAX_WORKERS = 8
SEG_TIMEOUT = (10, 60)      # (conexion, lectura) por segmento
SEG_ATTEMPTS = 3            # reintentos por segmento antes de abortar

# Probed once per process. Resolved lazily because importing this module must
# stay free of side effects, and ffmpeg may be installed after start-up.
_FFMPEG = None
_FFMPEG_PROBED = False


class HlsToolchainError(RuntimeError):
    """ffmpeg is not installed. Raised before any process is spawned."""


def _ffmpeg_path() -> str:
    """
    Return the absolute path to ffmpeg, or raise `HlsToolchainError`.

    Cached after the first probe: a missing ffmpeg cannot be fixed mid-run, and
    re-running `shutil.which()` on every download would only add latency.
    """
    global _FFMPEG, _FFMPEG_PROBED

    if not _FFMPEG_PROBED:
        _FFMPEG = find_ffmpeg()
        _FFMPEG_PROBED = True
        if _FFMPEG is None:
            logger.warning("ffmpeg not found; HLS downloads will fail")

    if _FFMPEG is None:
        raise HlsToolchainError(
            "ffmpeg no esta instalado. Instalalo y volve a intentar la descarga."
        )

    return _FFMPEG


def _formatear_bytes(b: int) -> str:
    if b < 1024:
        return f"{b} B"
    if b < 1024 ** 2:
        return f"{b / 1024:.1f} KB"
    if b < 1024 ** 3:
        return f"{b / 1024**2:.1f} MB"
    return f"{b / 1024**3:.2f} GB"


def _reportar(update_state, capitulo, fase, descargado, total, porcentaje):
    """Emite un evento de progreso si el caller paso estado y capitulo.

    Best-effort for real errors: a callback failure must not bring the download
    down. Cancellation is the one exception: `TaskCancelled` must keep
    propagating so the transfer actually aborts (a broad `except Exception`
    here used to swallow it and make HLS uncancellable).
    """
    if not update_state or capitulo is None:
        return
    try:
        update_state(state='PROGRESS', meta={
            'fase': fase,
            'capitulo': capitulo.nombre_archivo,
            'numero': capitulo.numero,
            'serie': capitulo.serie.nombre,
            'slug': capitulo.serie.slug,
            'fuente': capitulo.serie.fuente,
            'servidor': 'hls',
            'descargado': descargado,
            'total': total,
            'descargado_str': _formatear_bytes(descargado),
            'total_str': _formatear_bytes(total) if total > 0 else 'desconocido',
            'porcentaje': porcentaje,
        })
    except TaskCancelled:
        raise
    except Exception:
        pass


# ---------------------------------------------------------------------------
#  HTTP helpers (thread-local session para keep-alive entre segmentos)
# ---------------------------------------------------------------------------

_tls = threading.local()


def _session() -> requests.Session:
    s = getattr(_tls, "session", None)
    if s is None:
        s = requests.Session()
        s.headers.update({"User-Agent": USER_AGENT})
        _tls.session = s
    return s


def _fetch_text(url: str, headers: dict) -> str:
    resp = _session().get(url, headers=headers, timeout=(10, 60))
    resp.raise_for_status()
    return resp.text


def _fetch_bytes(url: str, headers: dict) -> bytes:
    last = None
    for _ in range(SEG_ATTEMPTS):
        try:
            resp = _session().get(url, headers=headers, timeout=SEG_TIMEOUT)
            resp.raise_for_status()
            return resp.content
        except Exception as e:  # noqa: BLE001 - reintentamos cualquier fallo de red
            last = e
    raise last


# ---------------------------------------------------------------------------
#  Manifest parsing
# ---------------------------------------------------------------------------

def _is_master(text: str) -> bool:
    return "#EXT-X-STREAM-INF" in text


def _parse_variants(text: str) -> list[tuple[int, str]]:
    """Devuelve [(bandwidth, uri)] de las variantes principales del master."""
    lines = text.splitlines()
    out = []
    for i, ln in enumerate(lines):
        if not ln.startswith("#EXT-X-STREAM-INF:"):
            continue
        bw = 0
        m = re.search(r"BANDWIDTH=(\d+)", ln)
        if m:
            bw = int(m.group(1))
        for j in range(i + 1, len(lines)):
            nxt = lines[j].strip()
            if nxt and not nxt.startswith("#"):
                out.append((bw, nxt))
                break
    return out


def _parse_segments(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]


def _needs_ffmpeg(text: str) -> bool:
    """True si el manifest no es concatenable a mano (cifrado, fMP4 o byterange)."""
    for ln in text.splitlines():
        if ln.startswith("#EXT-X-KEY") and "METHOD=NONE" not in ln:
            return True
        if ln.startswith("#EXT-X-MAP") or ln.startswith("#EXT-X-BYTERANGE"):
            return True
    return False


def _limpiar_part(filepath: Path):
    try:
        part = filepath.with_suffix('.part')
        if part.exists():
            part.unlink()
    except OSError:
        pass


# ---------------------------------------------------------------------------
#  Remux
# ---------------------------------------------------------------------------

def _ffmpeg_remux_local(src: Path, dst: Path) -> tuple[bool, str]:
    ffmpeg = _ffmpeg_path()
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-c", "copy", "-bsf:a", "aac_adtstoasc",
        "-movflags", "+faststart",
        "-f", "mp4", str(dst),
    ]
    result = subprocess.run(cmd, capture_output=True)
    ok = (
        result.returncode == 0
        and dst.exists()
        and dst.stat().st_size > 0
    )
    stderr = (result.stderr or b"").decode("utf-8", errors="replace").strip()
    return ok, stderr


# ---------------------------------------------------------------------------
#  Public API
# ---------------------------------------------------------------------------

def download_hls(
    url: str,
    filepath: str,
    referer: str | None = None,
    update_state=None,
    capitulo=None,
) -> tuple[bool, int]:
    """Descarga un manifest HLS y lo remuxea a MP4.

    Escribe a `<filepath>.part` y lo renombra al terminar, para que la limpieza
    de `.part` que ya existe en `tasks.py` siga funcionando ante cualquier fallo.

    Retorna `(exito, bytes_descargados)`, igual que `_stream_from_server`.
    """
    filepath = Path(filepath)
    headers = {}
    if referer:
        headers["Referer"] = referer

    try:
        ffmpeg = _ffmpeg_path()
    except HlsToolchainError as e:
        logger.warning(f"HLS: {e}")
        return False, 0

    _reportar(update_state, capitulo, 'descargando', 0, 0, 0)

    try:
        master = _fetch_text(url, headers)
        if _is_master(master):
            variants = _parse_variants(master)
            if not variants:
                raise RuntimeError("master sin variantes utilizables")
            variants.sort(key=lambda v: v[0], reverse=True)
            variant_url = urljoin(url, variants[0][1])
        else:
            variant_url = url

        variant = _fetch_text(variant_url, headers)

        if _needs_ffmpeg(variant):
            logger.info("HLS: manifest cifrado/fMP4; remux directo con ffmpeg")
            return _download_via_ffmpeg(ffmpeg, url, filepath, referer, update_state, capitulo)

        segments = [urljoin(variant_url, s) for s in _parse_segments(variant)]
        if not segments:
            return _download_via_ffmpeg(ffmpeg, url, filepath, referer, update_state, capitulo)

        return _download_segments(filepath, segments, headers, update_state, capitulo)

    except TaskCancelled:
        # Let cancellation escape: it must abort the download, not be turned
        # into a "try the next server" fallback.
        _limpiar_part(filepath)
        raise
    except Exception as e:  # noqa: BLE001 - cualquier fallo => descarga fallida
        logger.warning(f"HLS: error preparando la descarga: {e}")
        _limpiar_part(filepath)
        return False, 0


def _download_segments(
    filepath: Path,
    segments: list[str],
    headers: dict,
    update_state,
    capitulo,
) -> tuple[bool, int]:
    """Baja los segmentos en paralelo, los concatena y remuxea a MP4."""
    tmpdir = filepath.parent / f".{filepath.name}.hlstmp"
    shutil.rmtree(tmpdir, ignore_errors=True)
    tmpdir.mkdir(parents=True, exist_ok=True)

    total = len(segments)
    estado = {"done": 0, "bytes": 0}
    lock = threading.Lock()
    errores = []

    def bajar(i: int, seg: str):
        data = _fetch_bytes(seg, headers)
        (tmpdir / f"{i:06d}.ts").write_bytes(data)
        with lock:
            estado["done"] += 1
            estado["bytes"] += len(data)
            pct = int(estado["done"] * 100 / total)
            _reportar(update_state, capitulo, 'descargando', estado["bytes"], 0, pct)

    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = [ex.submit(bajar, i, s) for i, s in enumerate(segments)]
            for fut in as_completed(futures):
                exc = fut.exception()
                if exc:
                    errores.append(exc)
    except Exception as e:  # noqa: BLE001
        errores.append(e)

    # A cancellation raised inside a worker segment is captured by the future,
    # not by this thread: detect it first and re-raise so HLS aborts instead of
    # being reported as a failed segment (which would try the next server).
    cancelado = next((e for e in errores if isinstance(e, TaskCancelled)), None)
    if cancelado is not None:
        shutil.rmtree(tmpdir, ignore_errors=True)
        _limpiar_part(filepath)
        raise cancelado

    if errores:
        logger.warning(f"HLS: {len(errores)} segmento(s) fallaron: {errores[0]}")
        shutil.rmtree(tmpdir, ignore_errors=True)
        _limpiar_part(filepath)
        return False, 0

    concat = tmpdir / "all.ts"
    try:
        with open(concat, "wb") as out:
            for i in range(total):
                out.write((tmpdir / f"{i:06d}.ts").read_bytes())
    except Exception as e:  # noqa: BLE001
        logger.warning(f"HLS: error concatenando segmentos: {e}")
        shutil.rmtree(tmpdir, ignore_errors=True)
        _limpiar_part(filepath)
        return False, 0

    _reportar(update_state, capitulo, 'remux', estado["bytes"], 0, 100)

    part = filepath.with_suffix('.part')
    ok, err = _ffmpeg_remux_local(concat, part)
    shutil.rmtree(tmpdir, ignore_errors=True)

    if not ok or not part.exists() or part.stat().st_size == 0:
        logger.warning(f"HLS: remux local falló: {err[:300]}")
        _limpiar_part(filepath)
        return False, 0

    os.replace(part, filepath)
    size = os.path.getsize(filepath)
    _reportar(update_state, capitulo, 'descargando', size, size, 100)
    return True, size


def _download_via_ffmpeg(
    ffmpeg: str,
    url: str,
    filepath: Path,
    referer: str | None,
    update_state,
    capitulo,
) -> tuple[bool, int]:
    """Fallback: deja que ffmpeg baje y remuxee directo (entiende cifrado/fMP4).

    Es el camino lento en Windows (Schannel), pero solo se usa para manifests
    que no podemos concatenar a mano.
    """
    part = filepath.with_suffix('.part')

    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
    if referer:
        cmd += ["-headers", f"Referer: {referer}\r\nUser-Agent: {USER_AGENT}\r\n"]
    cmd += [
        "-i", url,
        "-c", "copy", "-bsf:a", "aac_adtstoasc",
        "-movflags", "+faststart",
        "-f", "mp4", str(part),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0 or not part.exists() or part.stat().st_size == 0:
            stderr = (result.stderr or b"").decode("utf-8", errors="replace").strip()
            logger.warning(f"HLS: ffmpeg (directo) falló (code {result.returncode}): {stderr[:300]}")
            _limpiar_part(filepath)
            return False, 0
        os.replace(part, filepath)
        size = os.path.getsize(filepath)
        _reportar(update_state, capitulo, 'descargando', size, size, 100)
        return True, size
    except TaskCancelled:
        _limpiar_part(filepath)
        raise
    except Exception as e:  # noqa: BLE001
        logger.warning(f"HLS: error ejecutando ffmpeg directo: {e}")
        _limpiar_part(filepath)
        return False, 0
