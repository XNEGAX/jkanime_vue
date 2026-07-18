"""
Celery tasks para descargas de episodios con progreso en tiempo real.
"""
import logging
from io import BytesIO
from pathlib import Path

import cloudscraper
import requests as _requests
from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils.dateparse import parse_datetime
from PIL import Image as PILImage
from requests.exceptions import ConnectionError as ReqConnectionError, Timeout as ReqTimeout

from . import scraper
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


def _limpiar_part(filepath: Path) -> None:
    part = filepath.with_suffix('.part')
    if part.exists():
        try:
            part.unlink()
        except OSError:
            pass


def _stream_from_server(
    server_info: dict,
    filepath: Path,
    update_state,
    capitulo: Capitulo,
) -> tuple[bool, int]:
    """Intenta descargar desde un servidor. Retorna (exitoso, bytes_descargados)."""
    headers = {}
    referer = scraper.REFERER_MAP.get(server_info['server'])
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
        return {'status': 'ok', 'message': 'El archivo ya existe', 'skip': True}

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
        download_urls = scraper.get_download_urls(capitulo.url_jkanime)
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


@shared_task(bind=True, time_limit=3600, soft_time_limit=3540, queue='descargas')
def descargar_capitulo(self, capitulo_id: int) -> dict:
    """Descarga un capitulo individual con progreso en tiempo real."""
    try:
        capitulo = Capitulo.objects.select_related('serie').get(id=capitulo_id)
    except Capitulo.DoesNotExist:
        return {'status': 'error', 'message': 'Capitulo no encontrado'}
    return _descargar_capitulo_core(capitulo, self.update_state)


@shared_task(bind=True, time_limit=7200, soft_time_limit=7140, queue='descargas')
def descargar_todos(self, serie_id: int) -> dict:
    """Descarga todos los capitulos faltantes de una serie."""
    try:
        serie = Serie.objects.prefetch_related('capitulos__serie').get(id=serie_id)
    except Serie.DoesNotExist:
        return {'status': 'error', 'message': 'Serie no encontrada'}

    capitulos_faltantes = [c for c in serie.capitulos.all() if not c.archivo_existe]

    if not capitulos_faltantes:
        return {'status': 'ok', 'message': 'No hay capitulos para descargar', 'completados': 0, 'fallidos': 0}

    total = len(capitulos_faltantes)
    completados = 0
    fallidos = 0
    total_bytes = 0

    for idx, cap in enumerate(capitulos_faltantes):
        self.update_state(state='PROGRESS', meta={
            'fase': 'descargando',
            'capitulo_actual': cap.nombre_archivo,
            'numero_actual': cap.numero,
            'indice': idx + 1,
            'total_capitulos': total,
            'completados': completados,
            'fallidos': fallidos,
            'total_bytes': total_bytes,
            'total_bytes_str': _formatear_bytes(total_bytes),
            'porcentaje_global': round(idx * 100 / total, 1) if total > 0 else 0,
        })

        try:
            resultado = _descargar_capitulo_core(cap, self.update_state)
            if resultado.get('status') == 'ok':
                completados += 1
                total_bytes += Path(cap.ruta_archivo).stat().st_size if cap.ruta_archivo else 0
            else:
                fallidos += 1

            self.update_state(state='PROGRESS', meta={
                'fase': 'completado_ep',
                'capitulo_actual': cap.nombre_archivo,
                'numero_actual': cap.numero,
                'indice': idx + 1,
                'total_capitulos': total,
                'completados': completados,
                'fallidos': fallidos,
                'total_bytes': total_bytes,
                'total_bytes_str': _formatear_bytes(total_bytes),
                'porcentaje_global': round((idx + 1) * 100 / total, 1) if total > 0 else 100,
            })
        except Exception as e:
            logger.error(f"Error capitulo {cap.numero}: {e}")
            fallidos += 1

    return {
        'status': 'ok',
        'message': f'Descarga completada: {completados} OK, {fallidos} fallidos',
        'completados': completados,
        'fallidos': fallidos,
        'total_bytes': total_bytes,
        'total_bytes_str': _formatear_bytes(total_bytes),
    }


@shared_task(bind=True, time_limit=3600, soft_time_limit=3540, queue='actualizaciones')
def verificar_series_task(self):
    """Scrapea JKanime: busca series nuevas, actualiza estado y dia_emision."""
    dias = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']

    # Fase 1: buscar series en la pagina principal
    self.update_state(state='PROGRESS', meta={
        'fase': 'buscando_series',
        'mensaje': 'Buscando series en JKanime...',
        'indice': 0,
        'total': 0,
    })

    try:
        series_jk = scraper.get_all_series_from_jkanime()
    except Exception as e:
        return {'status': 'error', 'message': f'Error obteniendo series: {e}'}

    if not series_jk:
        return {'status': 'error', 'message': 'No se encontraron series en JKanime'}

    existentes = set(Serie.objects.values_list('slug', flat=True))
    nuevas_creadas = 0

    # Fase 2: crear series nuevas
    total_jk = len(series_jk)
    for idx, s in enumerate(series_jk):
        if s['slug'] in existentes:
            continue

        self.update_state(state='PROGRESS', meta={
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

    # Fase 3: actualizar todas las series existentes
    todas = list(Serie.objects.all())
    actualizadas = 0
    total_todas = len(todas)

    for idx, serie in enumerate(todas):
        self.update_state(state='PROGRESS', meta={
            'fase': 'actualizando',
            'mensaje': f"Verificando: {serie.nombre}",
            'indice': idx + 1,
            'total': total_todas,
            'nombre': serie.nombre,
            'nuevas': nuevas_creadas,
            'actualizadas': actualizadas,
        })

        update_fields = []

        # Actualizar estado y dia_emision desde JKanime
        try:
            info = scraper.get_series_info_by_url(serie.url)
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

        # Fallback: si no se obtuvo dia_emision del scraper, derivarlo del ultimo capitulo
        if 'dia_emision' not in update_fields:
            ultimo_con_fecha = serie.capitulos.filter(
                fecha_publicacion__isnull=False
            ).order_by('-numero').first()

            if not ultimo_con_fecha:
                try:
                    eps_jk = scraper.get_episodes_for_series(serie.slug)
                    for ep in reversed(eps_jk):
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

        # Obtener episodios nuevos desde JKanime
        nuevos = 0
        try:
            eps_jk = scraper.get_episodes_for_series(serie.slug)
            eps_locales = {c.numero for c in serie.capitulos.all()}
            for ep in eps_jk:
                if ep['numero'] not in eps_locales:
                    defaults = {'url_jkanime': ep['url']}
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

    return {
        'status': 'ok',
        'message': f'Se encontraron {total_jk} series. {nuevas_creadas} nuevas. {actualizadas} actualizadas.',
        'nuevas': nuevas_creadas,
        'actualizadas': actualizadas,
        'total': total_jk,
    }
