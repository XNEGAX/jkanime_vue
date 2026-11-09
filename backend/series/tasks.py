"""
Core de descarga y verificacion — sin Celery.

Las funciones _run_* son llamadas desde los workers de task_runner.
El progreso se reporta via task_runner.update_task(task_id, ...).
"""

import logging
import os
import time
from io import BytesIO
from pathlib import Path

import cloudscraper
import requests as _requests
import urllib3
from django.core.files.base import ContentFile
from django.utils.dateparse import parse_datetime
from PIL import Image as PILImage

from . import server_stats
from requests.exceptions import ConnectionError as ReqConnectionError, Timeout as ReqTimeout

from .scrapers import get_scraper
from .scrapers.cf_clearance import allow_chrome_on_403
from .models import Capitulo, Serie
from .paths import serie_download_dir
from .ffmpeg_utils import find_ffmpeg

logger = logging.getLogger(__name__)

DOWNLOAD_TIMEOUT = 1200
CONNECT_TIMEOUT = 60
CHUNK_SIZE = 65536
PROGRESS_INTERVAL = 512 * 1024


def _formatear_bytes(b: int) -> str:
    if b < 1024:
        return f"{b} B"
    if b < 1024 ** 2:
        return f"{b / 1024:.1f} KB"
    if b < 1024 ** 3:
        return f"{b / 1024**2:.1f} MB"
    return f"{b / 1024**3:.2f} GB"


# Tamaño mínimo para considerar un MP4 válido (1 MB)
MIN_VALID_MP4_SIZE = 1 * 1024 * 1024


def _limpiar_part(filepath: Path) -> None:
    part = filepath.with_suffix('.part')
    if part.exists():
        try:
            part.unlink()
        except OSError:
            pass


def _validar_mp4(filepath: Path) -> tuple[bool, str]:
    """Valida que un archivo sea un MP4 reproducible.

    Revisa:
      - Tamaño mínimo (1 MB)
      - Cabecera MP4: debe contener 'ftyp' en los primeros 32 bytes
      - Debe tener un moov atom o mdat atom (no es un stub vacío)

    Retorna (valido, razon_si_invalido).
    """
    if not filepath.exists():
        return False, 'El archivo no existe'

    if filepath.stat().st_size < MIN_VALID_MP4_SIZE:
        return False, f'Archivo demasiado pequeño ({_formatear_bytes(filepath.stat().st_size)}) — descarga incompleta'

    try:
        with open(filepath, 'rb') as f:
            header = f.read(32)
    except OSError as e:
        return False, f'Error leyendo archivo: {e}'

    if len(header) < 8:
        return False, 'Archivo truncado — menos de 8 bytes'

    # Los primeros 4 bytes son el tamaño del primer box, los siguientes 4 son el tipo
    # Un MP4 válido debe tener 'ftyp' como primer box
    box_type = header[4:8]
    if box_type != b'ftyp':
        return False, f'Cabecera MP4 inválida (se esperaba ftyp, se encontró {box_type.decode("ascii", errors="replace")})'

    # Verificar que tenga moov o mdat (o al menos que no sea solo ftyp + vacío)
    try:
        with open(filepath, 'rb') as f:
            # Buscar 'moov' o 'mdat' en los primeros 100 KB
            probe = f.read(100 * 1024)
            if b'moov' not in probe and b'mdat' not in probe:
                return False, 'El archivo no contiene datos de video (sin moov/mdat)'
    except OSError:
        return False, 'Error al leer el archivo para validación'

    return True, ''


# FourCC de los sample entries de audio que puede contener un MP4. Se buscan
# los codecs y no el handler `soun` porque ese handler aparece igual en
# archivos sin ninguna pista de audio real (falso positivo comprobado).
_AUDIO_SAMPLE_ENTRIES = (b'mp4a', b'Opus', b'ac-3', b'ec-3', b'alac')


def _mp4_tiene_audio(filepath: Path) -> bool:
    """True si el MP4 declara una pista de audio con muestras.

    YouTube sirve video y audio como streams DASH separados, asi que bajar la
    URL directa de un formato de video produce un MP4 valido y completamente
    mudo. Revisar el atomo `moov` (al inicio con faststart, al final en el resto)
    evita guardar esos archivos como si la descarga hubiera salido bien.
    """
    def tiene_marcador(data: bytes) -> bool:
        return any(marcador in data for marcador in _AUDIO_SAMPLE_ENTRIES)

    try:
        size = filepath.stat().st_size
        ventana = 2 * 1024 * 1024
        with open(filepath, 'rb') as f:
            head = f.read(ventana)
            if tiene_marcador(head):
                return True
            if size > len(head):
                f.seek(max(0, size - ventana))
                return tiene_marcador(f.read())
    except OSError:
        return False
    return False


def _limpiar_restos_youtube(filepath: Path) -> None:
    """Borra temporales que yt-dlp deja si la descarga o el merge fallan."""
    restos = [Path(str(filepath) + '.part'), Path(str(filepath) + '.ytdl')]
    restos.extend(filepath.parent.glob(filepath.stem + '.f*'))
    for resto in restos:
        try:
            resto.unlink(missing_ok=True)
        except OSError:
            pass


def _descargar_youtube(capitulo: Capitulo, filepath: Path, update_state) -> tuple[bool, str]:
    """Descarga un capitulo de YouTube con yt-dlp, uniendo video y audio.

    YouTube ya no publica formatos progresivos (un solo archivo con imagen y
    sonido): todo es DASH, video por un lado y audio por otro. yt-dlp baja
    ambos y ffmpeg los mergea en el MP4 final.

    Retorna (exito, mensaje).
    """
    import yt_dlp

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return False, (
            'ffmpeg no esta instalado y YouTube sirve video y audio por separado. '
            'Instalalo (winget install Gyan.FFmpeg) y reinicia la app.'
        )

    serie = capitulo.serie
    _limpiar_restos_youtube(filepath)

    def reportar(fase, descargado, total):
        update_state(state='PROGRESS', meta={
            'fase': fase,
            'capitulo': capitulo.nombre_archivo,
            'numero': capitulo.numero,
            'serie': serie.nombre,
            'slug': serie.slug,
            'fuente': serie.fuente,
            'descargado': descargado,
            'total': total,
            'descargado_str': _formatear_bytes(descargado),
            'total_str': _formatear_bytes(total) if total else 'desconocido',
            'porcentaje': round(descargado * 100 / total, 1) if total else 0,
        })

    def progreso(d):
        if d.get('status') == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            reportar('descargando', d.get('downloaded_bytes') or 0, total)
        elif d.get('status') == 'finished':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            reportar('procesando', total, total)

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        # Nunca pedir un formato sin audio: `best[ext=mp4]` puede ser un DASH
        # de solo video segun el video, y eso era exactamente el bug.
        'format': (
            'bestvideo*[ext=mp4]+bestaudio[ext=m4a]'
            '/bestvideo*[ext=mp4]+bestaudio*'
            '/best[ext=mp4]/best'
        ),
        'merge_output_format': 'mp4',
        'outtmpl': str(filepath),
        'noplaylist': True,
        'ffmpeg_location': ffmpeg,
        'retries': 3,
        'fragment_retries': 3,
        'overwrites': True,
        'progress_hooks': [progreso],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([capitulo.url_fuente])
    except Exception as e:
        logger.error(f"YouTube: error descargando {capitulo.url_fuente}: {e}")
        _limpiar_restos_youtube(filepath)
        return False, f'Error de yt-dlp: {e}'

    if not filepath.exists():
        _limpiar_restos_youtube(filepath)
        return False, 'yt-dlp no genero el archivo final'

    valido, razon = _validar_mp4(filepath)
    if not valido:
        try:
            filepath.unlink()
        except OSError:
            pass
        _limpiar_restos_youtube(filepath)
        return False, f'El MP4 descargado no es valido: {razon}'

    if not _mp4_tiene_audio(filepath):
        # Nunca dejar un archivo mudo marcado como descarga exitosa.
        try:
            filepath.unlink()
        except OSError:
            pass
        _limpiar_restos_youtube(filepath)
        return False, 'El MP4 descargado no tiene pista de audio'

    return True, ''


def _stream_from_server(
    server_info: dict,
    filepath: Path,
    update_state,
    capitulo: Capitulo,
) -> tuple[bool, int]:
    """Intenta descargar desde un servidor. Retorna (exitoso, bytes_descargados)."""
    from .task_runner import TaskCancelled

    source_scraper = get_scraper(capitulo.serie.fuente)
    # ok.ru: re-resolver con embed fresco para evitar firma caducada
    if server_info.get('server') == 'Ok':
        try:
            from bs4 import BeautifulSoup
            import base64
            page = source_scraper._get_scraper().get(capitulo.url_fuente, timeout=60)
            soup = BeautifulSoup(page.text, "html.parser")
            embed = None
            for li in soup.select("li#play-video a.play-video"):
                b64 = li.get("data-player", "")
                if not b64:
                    continue
                try:
                    decoded = base64.b64decode(b64).decode("utf-8")
                except Exception:
                    continue
                if "ok.ru" in decoded:
                    embed = decoded
                    break
            if embed:
                from .scrapers.resolvers import resolve_okru
                fresh = resolve_okru(source_scraper._get_scraper(), embed)
                if fresh:
                    server_info['url'] = fresh
        except Exception:
            pass

    headers = {}
    referer = source_scraper.REFERER_MAP.get(server_info.get('server')) if server_info else None
    if server_info and server_info.get('server') == 'Ok':
        # usar el embed del episodio como referer (http)
        try:
            from bs4 import BeautifulSoup
            import base64
            page = source_scraper._get_scraper().get(capitulo.url_fuente, timeout=60)
            soup = BeautifulSoup(page.text, "html.parser")
            for li in soup.select("li#play-video a.play-video"):
                b64 = li.get("data-player", "")
                if not b64:
                    continue
                try:
                    decoded = base64.b64decode(b64).decode("utf-8")
                except Exception:
                    continue
                if "ok.ru" in decoded:
                    referer = decoded
                    break
        except Exception:
            referer = "http://ok.ru/videoembed/1885440969386"
    if referer:
        headers['Referer'] = referer

    # HLS (m3u8): un manifest no es un archivo descargable, hay que remuxearlo.
    if server_info.get('url') and '.m3u8' in server_info['url'].lower():
        from .downloaders.hls import download_hls
        return download_hls(
            server_info['url'],
            filepath,
            referer=headers.get('Referer'),
            update_state=update_state,
            capitulo=capitulo,
        )

    session = cloudscraper.create_scraper()
    try:
        # El connect-timeout tambien queda como timeout del socket para la
        # primera lectura, y Mp4upload tarda 7-30s en mandar el primer byte
        # (Vidhide y compania son igual de lentos para arrancar). Con 10s el
        # `read_timeout` efectivo era 10s y el capitulo fallaba siempre con
        # "Read timed out" a los pocos segundos. Por eso el connect va aparte,
        # holgado, y la lectura conserva DOWNLOAD_TIMEOUT.
        resp = session.get(
            server_info['url'],
            stream=True,
            timeout=urllib3.util.Timeout(connect=CONNECT_TIMEOUT, read=DOWNLOAD_TIMEOUT),
            headers=headers,
        )
        resp.raise_for_status()

        # Los servidores de latanime devuelven HTML (paginas de error/landing)
        # cuando el enlace no resuelve. Leerlas completas deja el worker colgado
        # hasta el read-timeout (20 min) porque suelen no cerrar la conexion.
        # Un video nunca viene como HTML/texto: si la respuesta no lo es, se
        # descarta el servidor al instante y se pasa al siguiente.
        content_type = (resp.headers.get('content-type') or '').lower()
        if content_type.startswith('text/') or 'html' in content_type or 'json' in content_type:
            logger.info(
                f"Servidor {server_info['server']} devolvio {content_type!r} "
                f"en vez de video; se omite"
            )
            resp.close()
            return False, 0

        # Un video real que se corta a mitad no debe bloquear al worker los
        # DOWNLOAD_TIMEOUT segundos completos: se acota la espera por lectura.
        try:
            if resp.raw._fp and hasattr(resp.raw._fp, '_sock') and resp.raw._fp._sock:
                resp.raw._fp._sock.settimeout(120)
        except Exception:
            pass

        total_size = int(resp.headers.get('content-length', 0))
        temp_path = filepath.with_suffix('.part')
        descargado = 0

        try:
            with open(temp_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    if not chunk:
                        continue
                    f.write(chunk)
                    descargado += len(chunk)

                    if total_size > 0 and descargado >= total_size:
                        update_state(state='PROGRESS', meta=_progreso_meta(
                            capitulo, server_info['server'], descargado, total_size, 100,
                        ))
                        break

                    if descargado % PROGRESS_INTERVAL < CHUNK_SIZE:
                        porcentaje = round(descargado * 100 / total_size, 1) if total_size > 0 else 0
                        update_state(state='PROGRESS', meta=_progreso_meta(
                            capitulo, server_info['server'], descargado, total_size, porcentaje,
                        ))
        except TaskCancelled:
            # Cancellation must abort THIS transfer, not fall through to the next
            # server. Re-raise before the broad handler so the signal survives.
            _limpiar_part(filepath)
            resp.close()
            raise
        except Exception as e:
            _limpiar_part(filepath)
            resp.close()
            logger.info(
                f"Descarga desde {server_info.get('server')} interrumpida tras "
                f"{descargado / 1048576:.1f} MB: {type(e).__name__}: {e}"
            )
            return False, 0

        resp.close()

        if temp_path.exists() and temp_path.stat().st_size > 0:
            os.replace(temp_path, filepath)
            return True, descargado

        _limpiar_part(filepath)
        return False, 0
    except ReqConnectionError:
        _limpiar_part(filepath)
        return False, 0
    except ReqTimeout:
        _limpiar_part(filepath)
        return False, 0
    except TaskCancelled:
        # Keep the cancellation signal alive across the generic handler below.
        _limpiar_part(filepath)
        raise
    except Exception:
        _limpiar_part(filepath)
        return False, 0
    finally:
        session.close()


def _progreso_meta(
    capitulo: Capitulo,
    servidor: str,
    descargado: int,
    total: int,
    porcentaje: float,
) -> dict:
    return {
        'fase': 'descargando',
        'capitulo': capitulo.nombre_archivo,
        'numero': capitulo.numero,
        'serie': capitulo.serie.nombre,
        'slug': capitulo.serie.slug,
        'fuente': capitulo.serie.fuente,
        'servidor': servidor,
        'descargado': descargado,
        'total': total,
        'descargado_str': _formatear_bytes(descargado),
        'total_str': _formatear_bytes(total) if total > 0 else 'desconocido',
        'porcentaje': porcentaje,
    }


def _descargar_capitulo_core(capitulo: Capitulo, update_state) -> dict:
    """Logica central de descarga: obtiene URLs, prueba servidores, guarda archivo."""
    ruta_existente = capitulo.ruta_archivo_real
    if ruta_existente:
        existente = Path(ruta_existente)
        # Validar que no este corrupto
        valido, razon = _validar_mp4(existente)
        # Un MP4 de YouTube sin pista de audio pasa el validador generico pero
        # es inutilizable: se trata como corrupto para volver a bajarlo.
        if valido and capitulo.serie.fuente == 'youtube' and not _mp4_tiene_audio(existente):
            valido, razon = False, 'el MP4 no tiene pista de audio'
        if valido:
            # Auto-sanado: persistir la ruta resuelta si la BD la tenia vacia.
            if capitulo.ruta_archivo != ruta_existente:
                capitulo.ruta_archivo = ruta_existente
                capitulo.save(update_fields=['ruta_archivo'])
            return {'status': 'ok', 'message': 'El archivo ya existe', 'skip': True}
        # Archivo corrupto: eliminarlo y continuar con la descarga
        logger.warning(f"Archivo corrupto detectado en descarga: {capitulo.nombre_archivo}: {razon}")
        try:
            existente.unlink()
        except OSError:
            pass
        # Nota: si el borrado falla (archivo bloqueado) la descarga igual lo
        # sobreescribe porque _stream_from_server usa os.replace.
        if not os.path.isfile(ruta_existente):
            capitulo.ruta_archivo = None
            capitulo.save(update_fields=['ruta_archivo'])

    update_state(state='PROGRESS', meta={
        'fase': 'buscando_servidores',
        'capitulo': capitulo.nombre_archivo,
        'numero': capitulo.numero,
        'serie': capitulo.serie.nombre,
        'slug': capitulo.serie.slug,
        'fuente': capitulo.serie.fuente,
        'descargado': 0,
        'total': 0,
        'descargado_str': '0 B',
        'total_str': '0 B',
        'porcentaje': 0,
    })

    serie_dir = serie_download_dir(capitulo.serie.slug, capitulo.serie.fuente)
    serie_dir.mkdir(parents=True, exist_ok=True)
    filepath = serie_dir / capitulo.nombre_archivo

    # YouTube: video y audio viajan en streams DASH separados, asi que bajar
    # una URL de `get_download_urls` guarda un MP4 mudo. Este camino baja
    # ambos con yt-dlp y los une con ffmpeg.
    if capitulo.serie.fuente == 'youtube':
        exito, detalle = _descargar_youtube(capitulo, filepath, update_state)
        if not exito:
            return {'status': 'error', 'message': detalle}

        capitulo.ruta_archivo = str(filepath)
        capitulo.serie.favorito = True
        capitulo.serie.save(update_fields=['favorito'])
        capitulo.save()
        return {
            'status': 'ok',
            'message': f'Descargado {capitulo.nombre_archivo}',
            'servidor': 'YouTube',
            'tamano': _formatear_bytes(filepath.stat().st_size),
        }

    try:
        s = get_scraper(capitulo.serie.fuente)
        download_urls = s.get_download_urls(capitulo.url_fuente)
        if not download_urls:
            return {'status': 'error', 'message': 'No se encontraron servidores de descarga'}
    except Exception as e:
        logger.error(f"Error obteniendo servidores para ep {capitulo.numero}: {e}")
        return {'status': 'error', 'message': f'Error obteniendo servidores: {e}'}

    # Candidates resolved by a real resolver (`resolved: True`) are direct media
    # links: try them first. Unresolved ones (landings/embeds) are a last
    # resort. `server_stats.rank` owns that guarantee (resolved-first) and adds
    # the learned per-server success rate as the ordering inside each group,
    # keeping the source's static SERVER_PRIORITY as the tiebreaker.
    # Candidates MISSING the key default to False (unverified) so a scraper that
    # forgets the flag can never be mistaken for a real media link.
    fuente = capitulo.serie.fuente
    candidatos = server_stats.rank(fuente, download_urls)

    for server_info in candidatos:
        servidor = server_info.get('server', '')
        # `ok` is the REAL outcome of this attempt: an exception mid-attempt, or
        # a stream that ends up invalid, must count as a failure. Recording lives
        # in the `finally` so it always lands exactly once per attempt.
        ok = False
        registrar = True
        try:
            exito, bytes_desc = _stream_from_server(server_info, filepath, update_state, capitulo)
            if exito:
                # Validar integridad del MP4 descargado
                valido, razon = _validar_mp4(filepath)
                if not valido:
                    logger.warning(
                        f"Archivo corrupto desde {server_info['server']} "
                        f"para {capitulo.nombre_archivo}: {razon}"
                    )
                    _limpiar_part(filepath.with_suffix('.part'))
                    try:
                        if filepath.exists():
                            filepath.unlink()
                    except OSError:
                        pass
                    continue  # Probar con el siguiente servidor (ok sigue False)

                ok = True
                capitulo.ruta_archivo = str(filepath)
                capitulo.serie.favorito = True
                capitulo.serie.save(update_fields=['favorito'])
                capitulo.save()
                return {
                    'status': 'ok',
                    'message': f'Descargado {capitulo.nombre_archivo}',
                    'servidor': server_info['server'],
                    'tamano': _formatear_bytes(filepath.stat().st_size),
                }
        except TaskCancelled:
            # User cancellation is not a server failure: a `fallo` here would
            # penalize a server for the user's choice. Let the signal propagate
            # so the worker's `finally` releases the in-flight slot, but skip the
            # stats write.
            registrar = False
            raise
        finally:
            if registrar:
                server_stats.record(fuente, servidor, ok)

    update_state(state='PROGRESS', meta={
        'fase': 'fallido',
        'capitulo': capitulo.nombre_archivo,
        'numero': capitulo.numero,
        'serie': capitulo.serie.nombre,
        'slug': capitulo.serie.slug,
        'fuente': capitulo.serie.fuente,
        'descargado': 0,
        'total': 0,
        'descargado_str': '0 B',
        'total_str': '0 B',
        'porcentaje': 0,
    })
    return {'status': 'error', 'message': 'Todos los servidores fallaron'}


# ---------------------------------------------------------------------------
# Entry points llamados desde task_runner workers
# ---------------------------------------------------------------------------


def _run_download(task_id: str, capitulo_id: int):
    """Descarga un capitulo individual con progreso."""
    from .task_runner import TaskCancelled, is_cancelled, release_download, update_task

    try:
        try:
            capitulo = Capitulo.objects.select_related('serie').get(id=capitulo_id)
        except Capitulo.DoesNotExist:
            update_task(task_id, state='FAILURE', message='Capitulo no encontrado')
            return

        def update_state(state, meta):
            update_task(task_id, state=state, **meta)
            if is_cancelled(task_id):
                # Dedicated exception (not StopIteration, see task_runner):
                # re-raised by every broad handler in the download chain so the
                # in-flight transfer aborts and the `finally` below releases
                # the slot once this worker has really exited.
                raise TaskCancelled("Tarea cancelada")

        try:
            resultado = _descargar_capitulo_core(capitulo, update_state)
            if resultado.get('status') == 'ok':
                update_task(task_id, state='SUCCESS', **resultado)
            else:
                update_task(task_id, state='FAILURE', **resultado)
        except TaskCancelled:
            update_task(task_id, state='CANCELLED', message='Cancelada por el usuario')
        except Exception as e:
            logger.exception(f"Error en descarga {capitulo_id}: {e}")
            update_task(task_id, state='FAILURE', message=str(e))
    finally:
        # El slot en vuelo se libera SIEMPRE, incluso por el camino de excepcion:
        # si no, el capitulo quedaria bloqueado para siempre. Es el unico lugar
        # que lo libera: `cancel_task()` no lo toca para no habilitar un segundo
        # worker mientras este sigue escribiendo.
        release_download(capitulo_id, task_id)


def _run_descargar_todos(task_id: str, serie_id: int):
    """Descarga todos los capitulos faltantes de una serie."""
    from .task_runner import is_cancelled, release_download, try_register_download, update_task

    try:
        serie = Serie.objects.prefetch_related('capitulos__serie').get(id=serie_id)
    except Serie.DoesNotExist:
        update_task(task_id, state='FAILURE', message='Serie no encontrada')
        return

    capitulos_faltantes = [c for c in serie.capitulos.all() if not c.archivo_existe]
    if not capitulos_faltantes:
        update_task(task_id, state='SUCCESS',
                     message='No hay capitulos para descargar',
                     completados=0, fallidos=0)
        return

    total = len(capitulos_faltantes)
    completados = 0
    fallidos = 0
    total_bytes = 0

    for idx, cap in enumerate(capitulos_faltantes):
        if is_cancelled(task_id):
            update_task(task_id, state='CANCELLED', message='Cancelada por el usuario')
            return

        # Saltar capitulos que ya estan en vuelo (una descarga individual, o una
        # corrida previa de descargar-todos). Reclamar el slot para esta tarea
        # evita que despues se le solape una descarga individual.
        if not try_register_download(cap.id, task_id):
            logger.info(f"Capitulo {cap.numero} ya en descarga; se omite")
            continue

        update_task(task_id, state='PROGRESS',
                     fase='descargando',
                     capitulo_actual=cap.nombre_archivo,
                     numero_actual=cap.numero,
                     indice=idx + 1,
                     total_capitulos=total,
                     completados=completados,
                     fallidos=fallidos,
                     total_bytes=total_bytes,
                     total_bytes_str=_formatear_bytes(total_bytes),
                     porcentaje_global=round(idx * 100 / total, 1) if total > 0 else 0)

        def update_state(state, meta):
            update_task(task_id, state=state, **meta)

        try:
            resultado = _descargar_capitulo_core(cap, update_state)
            if resultado.get('status') == 'ok':
                completados += 1
                ruta_real = cap.ruta_archivo_real
                total_bytes += Path(ruta_real).stat().st_size if ruta_real else 0
            else:
                fallidos += 1

            update_task(task_id, state='PROGRESS',
                         fase='completado_ep',
                         capitulo_actual=cap.nombre_archivo,
                         numero_actual=cap.numero,
                         indice=idx + 1,
                         total_capitulos=total,
                         completados=completados,
                         fallidos=fallidos,
                         total_bytes=total_bytes,
                         total_bytes_str=_formatear_bytes(total_bytes),
                         porcentaje_global=round((idx + 1) * 100 / total, 1) if total > 0 else 100)
        except Exception as e:
            logger.error(f"Error capitulo {cap.numero}: {e}")
            fallidos += 1
        finally:
            release_download(cap.id, task_id)

    update_task(task_id, state='SUCCESS',
                 message=f'Descarga completada: {completados} OK, {fallidos} fallidos',
                 completados=completados,
                 fallidos=fallidos,
                 total_bytes=total_bytes,
                 total_bytes_str=_formatear_bytes(total_bytes))


def _run_verificar(task_id: str):
    """Scrapea JKanime: busca series nuevas, actualiza estado y dia_emision."""
    from .task_runner import is_cancelled, update_task

    dias = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']

    def update_state(state, meta):
        update_task(task_id, state=state, **meta)

    update_state(state='PROGRESS', meta={
        'fase': 'buscando_series',
        'mensaje': 'Buscando series en JKanime...',
        'indice': 0,
        'total': 0,
    })

    # La verificación automática solo busca en JKanime
    jk = get_scraper('jkanime')

    try:
        series_jk = jk.get_all_series()
    except Exception as e:
        update_task(task_id, state='FAILURE', message=f'Error obteniendo series: {e}')
        return

    if not series_jk:
        update_task(task_id, state='FAILURE', message='No se encontraron series en JKanime')
        return

    existentes = set(Serie.objects.values_list('slug', flat=True))
    nuevas_creadas = 0

    total_jk = len(series_jk)
    for idx, s in enumerate(series_jk):
        if is_cancelled(task_id):
            update_task(task_id, state='CANCELLED', message='Verificacion cancelada')
            return

        if s['slug'] in existentes:
            continue

        update_state(state='PROGRESS', meta={
            'fase': 'creando_serie',
            'mensaje': f"Agregando: {s['nombre']}",
            'indice': idx + 1,
            'total': total_jk,
            'nombre': s['nombre'],
        })

        serie = Serie(nombre=s['nombre'], url=s['url'], slug=s['slug'])
        if s.get('cover_url'):
            try:
                resp = _requests.get(s['cover_url'], timeout=30)
                if resp.status_code == 200:
                    img = PILImage.open(BytesIO(resp.content))
                    buf = BytesIO()
                    img.save(buf, format='JPEG')
                    safe_name = s['slug'][:50]
                    serie.portada.save(f"{safe_name}.jpg", ContentFile(buf.getvalue()), save=False)
            except Exception as e:
                logger.warning(f"Error descargando portada para {s['nombre']}: {e}")
        serie.save()
        nuevas_creadas += 1

    todas = list(Serie.objects.all())
    actualizadas = 0
    total_todas = len(todas)

    for idx, serie in enumerate(todas):
        if is_cancelled(task_id):
            update_task(task_id, state='CANCELLED', message='Verificacion cancelada')
            return

        update_state(state='PROGRESS', meta={
            'fase': 'actualizando',
            'mensaje': f"Verificando: {serie.nombre}",
            'indice': idx + 1,
            'total': total_todas,
            'nombre': serie.nombre,
            'nuevas': nuevas_creadas,
            'actualizadas': actualizadas,
        })

        update_fields = []

        # Usar el scraper correspondiente a la fuente de la serie
        s = get_scraper(serie.fuente)

        try:
            info = s.get_series_info(serie.url)
            if info:
                if info.get('estado') and info['estado'] != serie.estado:
                    serie.estado = info['estado']
                    update_fields.append('estado')

                dia_scraped = info.get('dia_emision')
                if dia_scraped and dia_scraped != serie.dia_emision:
                    serie.dia_emision = dia_scraped
                    update_fields.append('dia_emision')
        except Exception:
            pass

        if 'dia_emision' not in update_fields:
            ultimo_con_fecha = serie.capitulos.filter(
                fecha_publicacion__isnull=False
            ).order_by('-numero').first()

            if not ultimo_con_fecha:
                try:
                    eps_fuente = s.get_episodes(serie.slug)
                    for ep in reversed(eps_fuente):
                        ts = ep.get('timestamp', '')
                        if ts:
                            parsed = parse_datetime(ts)
                            if parsed:
                                dia = dias[parsed.weekday()]
                                if dia != serie.dia_emision:
                                    serie.dia_emision = dia
                                    update_fields.append('dia_emision')
                                break
                except Exception:
                    pass
            else:
                dia = dias[ultimo_con_fecha.fecha_publicacion.weekday()]
                if dia != serie.dia_emision:
                    serie.dia_emision = dia
                    update_fields.append('dia_emision')

        nuevos = 0
        try:
            eps_fuente = s.get_episodes(serie.slug)
            eps_locales = {c.numero for c in serie.capitulos.all()}
            for ep in eps_fuente:
                if ep['numero'] not in eps_locales:
                    defaults = {'url_fuente': ep['url']}
                    ts = ep.get('timestamp', '')
                    if ts:
                        parsed = parse_datetime(ts)
                        if parsed:
                            defaults['fecha_publicacion'] = parsed
                    Capitulo.objects.get_or_create(
                        serie=serie, numero=ep['numero'], defaults=defaults,
                    )
                    nuevos += 1
        except Exception:
            pass

        hubo_cambios = bool(update_fields) or nuevos > 0
        if update_fields:
            serie.save(update_fields=update_fields)
        if hubo_cambios:
            actualizadas += 1

    update_task(task_id, state='SUCCESS',
                 message=f'Se encontraron {total_jk} series. {nuevas_creadas} nuevas. {actualizadas} actualizadas.',
                 nuevas=nuevas_creadas,
                 actualizadas=actualizadas,
                 total=total_jk)


def _run_verificar_estados(task_id: str):
    """Revalida estado/dia_emision SOLO de las series en emision.

    Delega en `actualizar_estado_serie`, que ya aplica el cooldown de
    REFRESH_ESTADO_HORAS: las series dentro del cooldown no se re-scrapean, y
    `verificacion_vencida` dice si a esta le tocaba intentarlo (que es lo que
    arma el ritmo del bucle).
    """
    from .task_runner import is_cancelled, update_task
    from .fuente import SCRAPE_DELAY_SEGUNDOS, actualizar_estado_serie, verificacion_vencida

    series = list(Serie.objects.filter(estado='en_emision'))
    total = len(series)
    reverificadas = 0

    def update_state(state, meta):
        update_task(task_id, state=state, **meta)

    update_state(state='PROGRESS', meta={
        'fase': 'revalidando_estados',
        'mensaje': 'Revalidando estados de series en emision...',
        'indice': 0,
        'total': total,
        'reverificadas': 0,
    })

    for idx, serie in enumerate(series):
        if is_cancelled(task_id):
            update_task(task_id, state='CANCELLED', message='Revalidacion cancelada')
            return

        update_state(state='PROGRESS', meta={
            'fase': 'revalidando_estados',
            'mensaje': f"Verificando: {serie.nombre}",
            'indice': idx + 1,
            'total': total,
            'nombre': serie.nombre,
            'reverificadas': reverificadas,
        })

        try:
            # La pausa va por INTENTO de scrape, no por exito: si la fuente
            # esta caida todos los intentos fallan, y sin esta pausa el bucle
            # la martilla 38 veces seguidas sin descanso. Con el cooldown ya no
            # se puede leer "hubo scrape" del valor de retorno (False tambien
            # significa "no habia nada que hacer"), por eso se pregunta antes.
            if verificacion_vencida(serie):
                time.sleep(SCRAPE_DELAY_SEGUNDOS)
            if actualizar_estado_serie(serie):
                reverificadas += 1
        except Exception as e:
            logger.warning(f"Error revalidando estado de {serie.slug}: {e}")

    update_task(task_id, state='SUCCESS',
                 message=f'{total} series en emision. {reverificadas} reverificadas contra la fuente.',
                 indice=total,
                 total=total,
                 reverificadas=reverificadas)


def _run_verificar_trending(task_id: str):
    """Busca episodios nuevos en el trending de JKanime y los persiste.

    Delega en `trending.sincronizar_trending`, que es la MISMA funcion que
    enrichment de `/api/ultimos-episodios/`: endpoint y tarea no pueden escribir
    distinto. La unica diferencia es el scrape, que va forzado (`force=True`)
    porque el endpoint se apoya en la cache de 30 min del trending y esta tarea
    corre cada hora justamente para no depender de ese TTL.

    `nuevos == 0` es el caso NORMAL, no un fallo: entre un chequeo y el siguiente
    la mayoria de las veces jkanime no publico nada. Por eso el cierre es
    SUCCESS siempre que el trending se haya leido.
    """
    from .task_runner import is_cancelled, update_task
    from .trending import sincronizar_trending

    def update_state(state, meta):
        update_task(task_id, state=state, **meta)

    update_state(state='PROGRESS', meta={
        'fase': 'consultando_trending',
        'mensaje': 'Consultando el trending de JKanime...',
        'indice': 0,
        'total': 0,
        'nuevos': 0,
    })

    try:
        scraper = get_scraper('jkanime')
        with allow_chrome_on_403():
            trending = scraper.get_trending(force=True)
    except Exception as e:
        update_task(task_id, state='FAILURE', mensaje=f'Error obteniendo trending: {e}')
        return

    # Trending vacio con `force=True` significa que la lectura fallo de verdad
    # (no hay cache de por medio): cero episodios no es un resultado valido, es
    # un scrape que no hay que reportar como exito.
    if not trending:
        update_task(task_id, state='FAILURE',
                    mensaje='El trending de JKanime vino vacio')
        return

    def al_progresar(indice, total, ep, nuevos):
        if is_cancelled(task_id):
            return False
        update_state(state='PROGRESS', meta={
            'fase': 'sincronizando_trending',
            'mensaje': f"Revisando: {ep.get('nombre') or ep.get('url', '')}",
            'indice': indice,
            'total': total,
            'nuevos': len(nuevos),
        })
        return True

    resultado = sincronizar_trending(trending, al_progresar=al_progresar)

    if resultado.get('cancelado'):
        update_task(task_id, state='CANCELLED', mensaje='Verificacion de trending cancelada')
        return

    nuevos = resultado['nuevos']
    total = resultado['total']
    update_task(task_id, state='SUCCESS',
                mensaje=f'{len(nuevos)} capitulos nuevos de {total} totales',
                message=f'{len(nuevos)} capitulos nuevos de {total} totales',
                indice=total,
                total=total,
                nuevos=len(nuevos),
                detalle=nuevos)


# ---------------------------------------------------------------------------
# YouTube Download — usando yt-dlp
# ---------------------------------------------------------------------------

def _download_with_yt_dlp(video_url: str, output_path: Path) -> tuple[bool, int]:
    """Descarga un video de YouTube usando yt-dlp y lo guarda como MP4.

    Retorna (exito, bytes_descargados).
    """
    import yt_dlp

    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': str(output_path) + '.part',
            'noplaylist': True,
            'merge_output_format': 'mp4',
            'continuedl': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            duration = info.get('duration', 0)
            title = info.get('title', 'Video de YouTube')

            # Descargar
            ydl.download([video_url])

            # Verificar que el archivo existe y es válido
            final_path = output_path
            part_path = Path(str(output_path) + '.part')

            if part_path.exists():
                # Validar MP4 (mínimo 1MB, header ftyp)
                if part_path.stat().st_size >= MIN_VALID_MP4_SIZE:
                    with open(part_path, 'rb') as f:
                        header = f.read(32)
                    if len(header) >= 8 and header[4:8] == b'ftyp':
                        # Mover a ubicación final
                        part_path.rename(final_path)
                        return True, part_path.stat().st_size
                else:
                    part_path.unlink(missing_ok=True)
                    return False, 0
            else:
                # Si yt-dlp ya renombró directamente a .mp4
                if final_path.exists():
                    if final_path.stat().st_size >= MIN_VALID_MP4_SIZE:
                        with open(final_path, 'rb') as f:
                            header = f.read(32)
                        if len(header) >= 8 and header[4:8] == b'ftyp':
                            return True, final_path.stat().st_size
                    return False, 0

        return False, 0
    except Exception as e:
        logger.error(f"Error descargando YouTube {video_url}: {e}")
        # Limpiar parziale si existe
        part_path = Path(str(output_path) + '.part')
        part_path.unlink(missing_ok=True)
        return False, 0


def _run_youtube_download(task_id: str, video_url: str, capitulo_numero: int, capitulo_title: str) -> dict:
    """Ejecuta la descarga de un capitulo desde YouTube.

    Args:
        task_id: ID de la tarea en curso
        video_url: URL del video de YouTube
        capitulo_numero: Número de capítulo
        capitulo_title: Título del capítulo

    Retorna dict con status y meta para update_task.
    """
    from .task_runner import is_cancelled, update_task, release_download

    # Determinar la serie y directorio de descarga
    # Necesitamos obtener la serie desde la BD - pero esta función
    # es llamada desde workers, así que usaremos la URL para inferir

    # Por ahora, usaremos una ruta basada en el número de capítulo
    # El caller debe proveer el slug y fuente appropriate
    # Por defecto, usaremos una carpeta temporal para pruebas

    import os
    from pathlib import Path

    # Ruta de salida: backend/descargas/youtube-Episodio-N.mp4
    # Usaremos un slug genérico por ahora
    download_dir = Path('backend/descargas/youtube-default')
    download_dir.mkdir(parents=True, exist_ok=True)

    output_file = download_dir / f"Episodios-{capitulo_numero}.mp4"

    # Verificar cancelación
    if is_cancelled(task_id):
        release_download(capitulo_numero, task_id) if 'capitulo_numero' in dir() else None
        update_task(task_id, state='CANCELLED', message='Cancelada por el usuario')
        return {'status': 'cancelled', 'message': 'Cancelada por el usuario'}

    # Ejecutar descarga
    success, bytes_downloaded = _download_with_yt_dlp(video_url, output_file)

    # Actualizar tarea
    if success:
        update_task(task_id, state='SUCCESS', meta={
            'fase': 'completado',
            'capitulo': capitulo_title,
            'numero': capitulo_numero,
            'serie': 'YouTube',
            'slug': 'youtube-default',
            'fuente': 'youtube',
            'descargado': bytes_downloaded,
            'total': bytes_downloaded,
            'descargado_str': _format_size(bytes_downloaded) if bytes_downloaded else '0 B',
            'total_str': _format_size(bytes_downloaded) if bytes_downloaded else '0 B',
            'porcentaje': 100,
        })
        message = f'Descargado {capitulo_title} de YouTube'
    else:
        update_task(task_id, state='FAILURE', meta={
            'fase': 'fallido',
            'capitulo': capitulo_title,
            'numero': capitulo_numero,
            'serie': 'YouTube',
            'slug': 'youtube-default',
            'fuente': 'youtube',
            'descargado': 0,
            'total': 0,
            'descargado_str': '0 B',
            'total_str': 'desconocido',
            'porcentaje': 0,
        })
        message = f'Error descargando {capitulo_title} de YouTube'

    return {'status': 'ok' if success else 'error', 'message': message}
