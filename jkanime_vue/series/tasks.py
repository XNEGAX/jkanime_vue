"""
Celery tasks para descargas de episodios con progreso en tiempo real.
"""
import os
import logging
import cloudscraper
from requests.exceptions import ConnectionError as ReqConnectionError, Timeout as ReqTimeout
from pathlib import Path

from celery import shared_task
from celery.states import SUCCESS, FAILURE

from django.conf import settings

from .models import Serie, Capitulo
from . import scraper

logger = logging.getLogger(__name__)

DOWNLOAD_TIMEOUT = 120


def _formatear_bytes(b):
    if b < 1024:
        return f"{b} B"
    elif b < 1024 ** 2:
        return f"{b / 1024:.1f} KB"
    elif b < 1024 ** 3:
        return f"{b / 1024**2:.1f} MB"
    return f"{b / 1024**3:.2f} GB"


def _limpiar_part(filepath):
    """Elimina archivos .part residuales."""
    part = filepath.with_suffix('.part')
    if part.exists():
        try:
            part.unlink()
        except OSError:
            pass


@shared_task(bind=True, time_limit=600, soft_time_limit=540, queue='descargas')
def descargar_capitulo(self, capitulo_id):
    """Descarga un capitulo individual con progreso en tiempo real."""
    try:
        capitulo = Capitulo.objects.select_related('serie').get(id=capitulo_id)
    except Capitulo.DoesNotExist:
        return {'status': 'error', 'message': 'Capitulo no encontrado'}

    if capitulo.archivo_existe:
        return {'status': 'ok', 'message': 'El archivo ya existe', 'skip': True}

    self.update_state(state='PROGRESS', meta={
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
        try:
            headers = {}
            referer = scraper.REFERER_MAP.get(server_info['server'])
            if referer:
                headers['Referer'] = referer

            session = cloudscraper.create_scraper()
            resp = session.get(
                server_info['url'],
                stream=True,
                timeout=(10, DOWNLOAD_TIMEOUT),
                headers=headers,
            )
            resp.raise_for_status()

            # Timeout en el socket para no quedarse pegado si el servidor deja de enviar
            try:
                if resp.raw._fp and hasattr(resp.raw._fp, '_sock') and resp.raw._fp._sock:
                    resp.raw._fp._sock.settimeout(30)
            except Exception:
                pass

            total_size = int(resp.headers.get('content-length', 0))
            temp_path = filepath.with_suffix('.part')
            descargado = 0

            try:
                with open(temp_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
                            descargado += len(chunk)

                            if total_size > 0 and descargado >= total_size:
                                porcentaje = 100
                                self.update_state(state='PROGRESS', meta={
                                    'fase': 'descargando',
                                    'capitulo': capitulo.nombre_archivo,
                                    'numero': capitulo.numero,
                                    'serie': capitulo.serie.nombre,
                                    'slug': capitulo.serie.slug,
                                    'servidor': server_info['server'],
                                    'descargado': descargado,
                                    'total': total_size,
                                    'descargado_str': _formatear_bytes(descargado),
                                    'total_str': _formatear_bytes(total_size),
                                    'porcentaje': 100,
                                })
                                break

                            if descargado % (512 * 1024) < 65536:
                                porcentaje = round(descargado * 100 / total_size, 1) if total_size > 0 else 0
                                self.update_state(state='PROGRESS', meta={
                                    'fase': 'descargando',
                                    'capitulo': capitulo.nombre_archivo,
                                    'numero': capitulo.numero,
                                    'serie': capitulo.serie.nombre,
                                    'slug': capitulo.serie.slug,
                                    'servidor': server_info['server'],
                                    'descargado': descargado,
                                    'total': total_size,
                                    'descargado_str': _formatear_bytes(descargado),
                                    'total_str': _formatear_bytes(total_size) if total_size > 0 else 'desconocido',
                                    'porcentaje': porcentaje,
                                })
            except Exception as e:
                logger.warning(f"Error durante descarga ep {capitulo.numero} desde {server_info['server']}: {e}")
                _limpiar_part(filepath)
                continue

            resp.close()
            session.close()

            if temp_path.exists() and temp_path.stat().st_size > 0:
                temp_path.rename(filepath)
                capitulo.ruta_archivo = str(filepath)
                capitulo.save()
                return {
                    'status': 'ok',
                    'message': f'Descargado {capitulo.nombre_archivo}',
                    'servidor': server_info['server'],
                    'tamano': _formatear_bytes(filepath.stat().st_size),
                }
            else:
                _limpiar_part(filepath)

        except ReqConnectionError as e:
            logger.warning(f"Conexion fallida ep {capitulo.numero} desde {server_info['server']}: {e}")
            _limpiar_part(filepath)
            continue
        except ReqTimeout:
            logger.warning(f"Timeout ep {capitulo.numero} desde {server_info['server']}")
            _limpiar_part(filepath)
            continue
        except Exception as e:
            logger.warning(f"Error descargando ep {capitulo.numero} desde {server_info['server']}: {e}")
            _limpiar_part(filepath)
            continue

    self.update_state(state='PROGRESS', meta={
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


@shared_task(bind=True, time_limit=7200, soft_time_limit=7140, queue='descargas')
def descargar_todos(self, serie_id):
    """Descarga todos los capitulos faltantes de una serie."""
    try:
        serie = Serie.objects.get(id=serie_id)
    except Serie.DoesNotExist:
        return {'status': 'error', 'message': 'Serie no encontrada'}

    capitulos_faltantes = [
        c for c in serie.capitulos.all()
        if not c.archivo_existe
    ]

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
            if cap.archivo_existe:
                completados += 1
                continue

            download_urls = scraper.get_download_urls(cap.url_jkanime)
            if not download_urls:
                fallidos += 1
                continue

            download_dir = Path(settings.DOWNLOAD_DIR)
            serie_dir = download_dir / cap.serie.slug
            serie_dir.mkdir(parents=True, exist_ok=True)
            filepath = serie_dir / cap.nombre_archivo

            descargado = False
            for server_info in download_urls:
                try:
                    headers = {}
                    referer = scraper.REFERER_MAP.get(server_info['server'])
                    if referer:
                        headers['Referer'] = referer

                    session = cloudscraper.create_scraper()
                    resp = session.get(
                        server_info['url'],
                        stream=True,
                        timeout=(10, DOWNLOAD_TIMEOUT),
                        headers=headers,
                    )
                    resp.raise_for_status()

                    # Timeout en el socket
                    try:
                        if resp.raw._fp and hasattr(resp.raw._fp, '_sock') and resp.raw._fp._sock:
                            resp.raw._fp._sock.settimeout(30)
                    except Exception:
                        pass

                    total_size_ep = int(resp.headers.get('content-length', 0))
                    temp_path = filepath.with_suffix('.part')
                    bytes_ep = 0

                    try:
                        with open(temp_path, 'wb') as f:
                            for chunk in resp.iter_content(chunk_size=65536):
                                if chunk:
                                    f.write(chunk)
                                    bytes_ep += len(chunk)
                                    if total_size_ep > 0 and bytes_ep >= total_size_ep:
                                        break
                    except Exception as e:
                        logger.warning(f"Error descarga ep {cap.numero} desde {server_info['server']}: {e}")
                        _limpiar_part(filepath)
                        continue

                    resp.close()
                    session.close()

                    if temp_path.exists() and temp_path.stat().st_size > 0:
                        temp_path.rename(filepath)
                        cap.ruta_archivo = str(filepath)
                        cap.save()
                        completados += 1
                        total_bytes += bytes_ep
                        descargado = True

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
                        break
                    else:
                        _limpiar_part(filepath)

                except ReqConnectionError:
                    _limpiar_part(filepath)
                    continue
                except ReqTimeout:
                    _limpiar_part(filepath)
                    continue
                except Exception as e:
                    logger.warning(f"Error ep {cap.numero} desde {server_info['server']}: {e}")
                    _limpiar_part(filepath)
                    continue

            if not descargado:
                fallidos += 1

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
    from django.utils.dateparse import parse_datetime
    from io import BytesIO

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
                import requests as req
                resp = req.get(s['cover_url'], timeout=30)
                if resp.status_code == 200:
                    from PIL import Image as PILImage
                    from django.core.files.base import ContentFile
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

        # Actualizar estado desde JKanime
        try:
            info = scraper.get_series_info_by_url(serie.url)
            if info and info.get('estado') and info['estado'] != serie.estado:
                serie.estado = info['estado']
                update_fields.append('estado')
        except Exception:
            pass

        # Actualizar dia_emision
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

        if update_fields:
            serie.save(update_fields=update_fields)
            actualizadas += 1

    return {
        'status': 'ok',
        'message': f'Se encontraron {total_jk} series. {nuevas_creadas} nuevas. {actualizadas} actualizadas.',
        'nuevas': nuevas_creadas,
        'actualizadas': actualizadas,
        'total': total_jk,
    }
