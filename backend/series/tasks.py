"""
Core de descarga y verificacion — sin Celery.

Las funciones _run_* son llamadas desde los workers de task_runner.
El progreso se reporta via task_runner.update_task(task_id, ...).
"""

import logging
from io import BytesIO
from pathlib import Path

import cloudscraper
import requests as _requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils.dateparse import parse_datetime
from PIL import Image as PILImage
from requests.exceptions import ConnectionError as ReqConnectionError, Timeout as ReqTimeout

from .scrapers import get_scraper
from .models import Capitulo, Serie

logger = logging.getLogger(__name__)

DOWNLOAD_TIMEOUT = 1200
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


def _stream_from_server(
    server_info: dict,
    filepath: Path,
    update_state,
    capitulo: Capitulo,
) -> tuple[bool, int]:
    """Intenta descargar desde un servidor. Retorna (exitoso, bytes_descargados)."""
    headers = {}
    from .scrapers.jkanime import JKanimeScraper
    referer = JKanimeScraper.REFERER_MAP.get(server_info['server'])
    if referer:
        headers['Referer'] = referer

    session = cloudscraper.create_scraper()
    try:
        resp = session.get(
            server_info['url'],
            stream=True,
            timeout=(10, DOWNLOAD_TIMEOUT),
            headers=headers,
        )
        resp.raise_for_status()

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
        except Exception:
            _limpiar_part(filepath)
            resp.close()
            return False, 0

        resp.close()

        if temp_path.exists() and temp_path.stat().st_size > 0:
            temp_path.rename(filepath)
            return True, descargado

        _limpiar_part(filepath)
        return False, 0
    except ReqConnectionError:
        _limpiar_part(filepath)
        return False, 0
    except ReqTimeout:
        _limpiar_part(filepath)
        return False, 0
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
        'servidor': servidor,
        'descargado': descargado,
        'total': total,
        'descargado_str': _formatear_bytes(descargado),
        'total_str': _formatear_bytes(total) if total > 0 else 'desconocido',
        'porcentaje': porcentaje,
    }


def _descargar_capitulo_core(capitulo: Capitulo, update_state) -> dict:
    """Logica central de descarga: obtiene URLs, prueba servidores, guarda archivo."""
    if capitulo.archivo_existe:
        # Validar que no este corrupto
        valido, razon = _validar_mp4(Path(capitulo.ruta_archivo))
        if valido:
            return {'status': 'ok', 'message': 'El archivo ya existe', 'skip': True}
        # Archivo corrupto: eliminarlo y continuar con la descarga
        logger.warning(f"Archivo corrupto detectado en descarga: {capitulo.nombre_archivo}: {razon}")
        try:
            if capitulo.ruta_archivo and Path(capitulo.ruta_archivo).exists():
                Path(capitulo.ruta_archivo).unlink()
        except OSError:
            pass
        capitulo.ruta_archivo = None
        capitulo.save(update_fields=['ruta_archivo'])

    update_state(state='PROGRESS', meta={
        'fase': 'buscando_servidores',
        'capitulo': capitulo.nombre_archivo,
        'numero': capitulo.numero,
        'serie': capitulo.serie.nombre,
        'slug': capitulo.serie.slug,
        'descargado': 0,
        'total': 0,
        'descargado_str': '0 B',
        'total_str': '0 B',
        'porcentaje': 0,
    })

    try:
        s = get_scraper(capitulo.serie.fuente)
        download_urls = s.get_download_urls(capitulo.url_fuente)
        if not download_urls:
            return {'status': 'error', 'message': 'No se encontraron servidores de descarga'}
    except Exception as e:
        logger.error(f"Error obteniendo servidores para ep {capitulo.numero}: {e}")
        return {'status': 'error', 'message': f'Error obteniendo servidores: {e}'}

    download_dir = Path(settings.DOWNLOAD_DIR)
    serie_dir = download_dir / capitulo.serie.slug
    serie_dir.mkdir(parents=True, exist_ok=True)
    filepath = serie_dir / capitulo.nombre_archivo

    for server_info in download_urls:
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
                continue  # Probar con el siguiente servidor

            capitulo.ruta_archivo = str(filepath)
            capitulo.save()
            return {
                'status': 'ok',
                'message': f'Descargado {capitulo.nombre_archivo}',
                'servidor': server_info['server'],
                'tamano': _formatear_bytes(filepath.stat().st_size),
            }

    update_state(state='PROGRESS', meta={
        'fase': 'fallido',
        'capitulo': capitulo.nombre_archivo,
        'numero': capitulo.numero,
        'serie': capitulo.serie.nombre,
        'slug': capitulo.serie.slug,
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
    from .task_runner import is_cancelled, update_task

    try:
        capitulo = Capitulo.objects.select_related('serie').get(id=capitulo_id)
    except Capitulo.DoesNotExist:
        update_task(task_id, state='FAILURE', message='Capitulo no encontrado')
        return

    def update_state(state, meta):
        update_task(task_id, state=state, **meta)
        if is_cancelled(task_id):
            raise StopIteration("Tarea cancelada")

    try:
        resultado = _descargar_capitulo_core(capitulo, update_state)
        if resultado.get('status') == 'ok':
            update_task(task_id, state='SUCCESS', **resultado)
        else:
            update_task(task_id, state='FAILURE', **resultado)
    except StopIteration:
        update_task(task_id, state='CANCELLED', message='Cancelada por el usuario')
    except Exception as e:
        logger.exception(f"Error en descarga {capitulo_id}: {e}")
        update_task(task_id, state='FAILURE', message=str(e))


def _run_descargar_todos(task_id: str, serie_id: int):
    """Descarga todos los capitulos faltantes de una serie."""
    from .task_runner import is_cancelled, update_task

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
                total_bytes += Path(cap.ruta_archivo).stat().st_size if cap.ruta_archivo else 0
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
