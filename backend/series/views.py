"""
REST API views for jkanime_vue.

Tareas en background via threading (task_runner) en vez de Celery + Redis.
"""

import glob
import hashlib
import logging
import os
import re
from io import BytesIO
from pathlib import Path

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.http import FileResponse, Http404, HttpResponseNotModified
from django.utils.dateparse import parse_datetime
from django.utils.http import http_date
from PIL import Image as PILImage
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .scrapers import get_scraper
from . import task_runner
from .models import Capitulo, Serie
from .serializers import (
    CapituloDetailSerializer,
    CapituloSerializer,
    SerieDetailSerializer,
    SerieListSerializer,
)

logger = logging.getLogger(__name__)


# ===========================================================================
#  Series
# ===========================================================================

@api_view(['GET'])
def api_series_favoritos(request):
    """Lista series favoritas, opcionalmente filtradas por estado, dia de emision o letra inicial."""
    from django.db.models import Q

    series = Serie.objects.filter(favorito=True)
    estado = request.query_params.get('estado', '').strip()
    if estado:
        series = series.filter(estado=estado)
    dia = request.query_params.get('dia', '').strip()
    if dia:
        series = series.filter(dia_emision=dia)
    letras = request.query_params.get('letras', '').strip()
    if letras:
        filtro = Q()
        for letra in letras:
            filtro |= Q(nombre__istartswith=letra)
        series = series.filter(filtro)
    serializer = SerieListSerializer(series, many=True, context={'request': request})
    return Response(serializer.data)


@api_view(['POST'])
def api_toggle_favorito(request, serie_id):
    """Alterna el estado de favorito de una serie."""
    try:
        serie = Serie.objects.get(id=serie_id)
    except Serie.DoesNotExist:
        return Response({'error': 'Serie no encontrada'}, status=status.HTTP_404_NOT_FOUND)
    serie.favorito = not serie.favorito
    serie.save(update_fields=['favorito'])
    return Response({'favorito': serie.favorito})


@api_view(['DELETE'])
def api_eliminar_serie(request, serie_id):
    """Elimina una serie, sus capitulos y archivos del disco."""
    try:
        serie = Serie.objects.prefetch_related('capitulos').get(id=serie_id)
    except Serie.DoesNotExist:
        return Response({'error': 'Serie no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    delete_errors = []
    for cap in serie.capitulos.all():
        if cap.ruta_archivo and os.path.isfile(cap.ruta_archivo):
            try:
                os.remove(cap.ruta_archivo)
            except OSError as e:
                delete_errors.append(f'Error eliminando {cap.ruta_archivo}: {e}')

    if serie.portada and os.path.isfile(serie.portada.path):
        try:
            serie.portada.delete(save=False)
        except OSError as e:
            delete_errors.append(f'Error eliminando portada: {e}')

    serie.delete()

    if delete_errors:
        return Response({
            'mensaje': 'Serie eliminada con algunos errores',
            'errores': delete_errors,
        }, status=status.HTTP_200_OK)

    return Response({'mensaje': 'Serie eliminada correctamente'})


@api_view(['GET'])
def api_serie_detail(request, serie_id):
    """Detalle de una serie con sus capitulos."""
    try:
        serie = Serie.objects.prefetch_related('capitulos').get(id=serie_id)
    except Serie.DoesNotExist:
        return Response({'error': 'Serie no encontrada'}, status=status.HTTP_404_NOT_FOUND)
    serializer = SerieDetailSerializer(serie, context={'request': request})
    return Response(serializer.data)


# ===========================================================================
#  Capitulos
# ===========================================================================


@api_view(['GET'])
def api_capitulos(request, serie_id):
    """Lista capitulos de una serie (scrapea JKanime para nuevos)."""
    try:
        serie = Serie.objects.get(id=serie_id)
    except Serie.DoesNotExist:
        return Response({'error': 'Serie no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    try:
        s = get_scraper(serie.fuente)
        eps = s.get_episodes(serie.slug)
        eps_locales = {c.numero for c in serie.capitulos.all()}

        nuevos = [ep for ep in eps if ep['numero'] not in eps_locales]

        for ep in nuevos:
            defaults = {'url_fuente': ep['url']}
            ts = ep.get('timestamp', '')
            if ts:
                parsed = parse_datetime(ts)
                if parsed:
                    defaults['fecha_publicacion'] = parsed
            Capitulo.objects.get_or_create(
                serie=serie,
                numero=ep['numero'],
                defaults=defaults,
            )

        # Actualizar estado y dia de emision desde la fuente
        try:
            info = s.get_series_info(serie.url)
            if info:
                changes = []
                if info.get('estado') and info['estado'] != serie.estado:
                    serie.estado = info['estado']
                    changes.append('estado')
                dia_scraped = info.get('dia_emision')
                if dia_scraped and dia_scraped != serie.dia_emision:
                    serie.dia_emision = dia_scraped
                    changes.append('dia_emision')
                if changes:
                    serie.save(update_fields=changes)
        except Exception:
            pass

        capitulos = serie.capitulos.select_related('serie').order_by('numero')
        serializer = CapituloSerializer(capitulos, many=True)

        return Response({
            'capitulos': serializer.data,
            'nuevos_encontrados': len(nuevos),
            'total_fuente': len(eps),
        })
    except Exception as e:
        logger.error(f"Error en API de capitulos para {serie.nombre}: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def api_capitulo_detail(request, capitulo_id):
    """Detalle de un capitulo."""
    try:
        cap = Capitulo.objects.select_related('serie').get(id=capitulo_id)
    except Capitulo.DoesNotExist:
        return Response({'error': 'Capitulo no encontrado'}, status=status.HTTP_404_NOT_FOUND)
    serializer = CapituloDetailSerializer(cap)
    return Response(serializer.data)


@api_view(['POST'])
def api_guardar_progreso(request, capitulo_id):
    """Guarda el ultimo segundo visto de un capitulo."""
    try:
        cap = Capitulo.objects.get(id=capitulo_id)
    except Capitulo.DoesNotExist:
        return Response({'error': 'Capitulo no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    segundo = request.data.get('segundo', 0)
    try:
        segundo = max(0, int(segundo))
    except (TypeError, ValueError):
        segundo = 0

    cap.ultimo_segundo = segundo
    cap.save(update_fields=['ultimo_segundo'])
    return Response({'status': 'ok'})


# ===========================================================================
#  Descargas
# ===========================================================================


@api_view(['POST'])
def api_descargar_capitulo(request, capitulo_id):
    """Inicia descarga de un capitulo via task_runner."""
    try:
        capitulo = Capitulo.objects.get(id=capitulo_id)
    except Capitulo.DoesNotExist:
        return Response({'error': 'Capitulo no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    if capitulo.archivo_existe:
        # Validar que no este corrupto antes de saltar
        from .tasks import _validar_mp4
        valido, razon = _validar_mp4(Path(capitulo.ruta_archivo))
        if valido:
            return Response({'status': 'ok', 'message': 'Ya existe', 'skip': True})
        # Archivo corrupto: eliminar y descargar de nuevo
        logger.warning(f"Archivo corrupto detectado en {capitulo.nombre_archivo}: {razon}")
        try:
            os.remove(capitulo.ruta_archivo)
        except OSError:
            pass
        capitulo.ruta_archivo = None
        capitulo.save(update_fields=['ruta_archivo'])

    task_id = task_runner.enqueue_download(capitulo_id)
    return Response({
        'status': 'ok',
        'message': f'Descarga iniciada: {capitulo.nombre_archivo}',
        'task_id': task_id,
        'corrupto_reparado': True,
    })


@api_view(['POST'])
def api_descargar_todos(request, serie_id):
    """
    Lanza descargas individuales para cada capitulo faltante.
    Cada capitulo va a la cola como tarea separada -> los 10 workers
    las procesan en paralelo.
    """
    try:
        serie = Serie.objects.get(id=serie_id)
    except Serie.DoesNotExist:
        return Response({'error': 'Serie no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    capitulos_faltantes = [c for c in serie.capitulos.all() if not c.archivo_existe]
    if not capitulos_faltantes:
        return Response({'status': 'ok', 'message': 'No hay capitulos para descargar'})

    tasks = []
    for cap in capitulos_faltantes:
        task_id = task_runner.enqueue_download(cap.id)
        tasks.append({
            'task_id': task_id,
            'capitulo_id': cap.id,
            'numero': cap.numero,
        })

    return Response({
        'status': 'ok',
        'message': f'Descarga iniciada: {len(tasks)} capitulos',
        'tasks': tasks,
        'total': len(tasks),
    })


# ===========================================================================
#  Verificacion
# ===========================================================================


@api_view(['GET', 'POST'])
def api_verificar_series(request):
    """POST: lanza verificacion en background. GET: devuelve estado de la tarea activa."""
    from .task_runner import _verificacion_task_id

    if request.method == 'GET':
        tid = _verificacion_task_id
        if not tid:
            return Response({'state': 'NONE'})
        task = task_runner.get_task(tid)
        if not task:
            return Response({'state': 'NONE'})
        data = {'state': task.get('state', 'NONE'), **{k: v for k, v in task.items() if k not in ('task_id',)}}
        resp = Response(data)
        resp['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return resp

    # POST
    tid = _verificacion_task_id
    if tid:
        task = task_runner.get_task(tid)
        if task and task.get('state') in ('PENDING', 'PROGRESS'):
            return Response({
                'status': 'already_running',
                'task_id': tid,
                **{k: v for k, v in task.items() if k not in ('task_id',)},
            })

    new_tid = task_runner.enqueue_verificar()
    if not new_tid:
        return Response({'status': 'already_running'})
    return Response({'status': 'started', 'task_id': new_tid})


# ===========================================================================
#  Agregar serie por URL
# ===========================================================================


@api_view(['POST'])
def api_agregar_serie_url(request):
    """Agrega una serie desde una URL directa de JKanime o Latanime."""
    url = request.data.get('url', '').strip()
    if not url:
        return Response({'error': 'Se requiere una URL'}, status=status.HTTP_400_BAD_REQUEST)

    # Detectar fuente
    fuente = None
    slug = None
    if re.search(r'jkanime\.net', url):
        fuente = 'jkanime'
        match = re.search(r'jkanime\.net/([^/\s?#]+)', url)
        if match:
            slug = match.group(1)
    elif re.search(r'latanime\.org', url):
        fuente = 'latanime'
        # Para Latanime, la URL es /anime/<slug>
        match = re.search(r'latanime\.org/(?:anime|ver)/([^/\s?#]+)', url)
        if match:
            slug = match.group(1)
    else:
        return Response({
            'error': 'URL no válida. Debe ser de jkanime.net o latanime.org'
        }, status=status.HTTP_400_BAD_REQUEST)

    if not slug:
        return Response({
            'error': 'No se pudo extraer el slug de la URL'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Verificar si ya existe por slug (namespace por fuente para evitar colisiones)
    if Serie.objects.filter(slug=slug, fuente=fuente).exists():
        serie = Serie.objects.get(slug=slug, fuente=fuente)
        return Response({
            'status': 'ok',
            'message': f'"{serie.nombre}" ya está en la lista',
            'serie_id': serie.id,
            'existing': True,
        })

    s = get_scraper(fuente)
    info = s.get_series_info(url)
    if not info:
        return Response({
            'error': 'No se pudo obtener info de la serie. Verifica la URL.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    serie = Serie(
        nombre=info['nombre'],
        url=f"{s.BASE_URL}/anime/{info['slug']}" if fuente == 'latanime' else f"{s.BASE_URL}/{info['slug']}/",
        slug=info['slug'],
        estado=info.get('estado', 'desconocido'),
        fuente=fuente,
    )

    if info.get('cover_url'):
        try:
            headers = {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/125.0.0.0 Safari/537.36'
                ),
                'Referer': 'https://latanime.org/',
            }
            resp = requests.get(info['cover_url'], timeout=30, headers=headers)
            if resp.status_code == 200:
                img = PILImage.open(BytesIO(resp.content))
                buf = BytesIO()
                img.save(buf, format='JPEG')
                serie.portada.save(f"{info['slug'][:50]}.jpg", ContentFile(buf.getvalue()), save=False)
        except Exception as e:
            logger.warning(f"Error descargando portada: {e}")

    serie.save()

    eps = s.get_episodes(info['slug'])
    for ep in eps:
        defaults = {'url_fuente': ep['url']}
        ts = ep.get('timestamp', '')
        if ts:
            parsed = parse_datetime(ts)
            if parsed:
                defaults['fecha_publicacion'] = parsed
        Capitulo.objects.get_or_create(
            serie=serie,
            numero=ep['numero'],
            defaults=defaults,
        )

    return Response({
        'status': 'ok',
        'message': f'Serie "{info["nombre"]}" agregada con {len(eps)} capítulos',
        'serie_id': serie.id,
        'fuente': fuente,
        'capitulos': len(eps),
    })


# ===========================================================================
#  Refrescar portada
# ===========================================================================


@api_view(['POST'])
def api_refrescar_portada(request, serie_id):
    """Descarga/refresca la portada de una serie existente desde su fuente."""
    try:
        serie = Serie.objects.get(id=serie_id)
    except Serie.DoesNotExist:
        return Response({'error': 'Serie no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    s = get_scraper(serie.fuente)
    info = s.get_series_info(serie.url)
    if not info or not info.get('cover_url'):
        return Response({
            'error': 'No se pudo obtener la URL de la portada desde la fuente'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    try:
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/125.0.0.0 Safari/537.36'
            ),
            'Referer': f'{s.BASE_URL}/',
        }
        resp = requests.get(info['cover_url'], timeout=30, headers=headers)
        if resp.status_code == 200:
            img = PILImage.open(BytesIO(resp.content))
            buf = BytesIO()
            img.save(buf, format='JPEG')
            safe_name = serie.slug[:50] or info['slug'][:50]
            serie.portada.save(f"{safe_name}.jpg", ContentFile(buf.getvalue()), save=False)
            serie.save(update_fields=['portada'])

            portada_url = request.build_absolute_uri(serie.portada.url) if serie.portada else None
            return Response({'status': 'ok', 'portada_url': portada_url})
        else:
            return Response({
                'error': f'Error HTTP {resp.status_code} descargando la imagen'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        logger.warning(f"Error descargando portada para {serie.nombre}: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===========================================================================
#  Estado de tareas
# ===========================================================================


@api_view(['GET'])
def api_estado_tarea(request, task_id):
    """Estado y progreso de una tarea."""
    task = task_runner.get_task(task_id)
    if not task:
        return Response({'state': 'NONE'})
    data = {k: v for k, v in task.items() if k != 'task_id'}
    resp = Response(data)
    resp['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp['Pragma'] = 'no-cache'
    resp['Expires'] = '0'
    return resp


@api_view(['GET'])
def api_tareas_activas(request):
    """Devuelve tareas en ejecucion o en cola."""
    tasks = task_runner.get_active_tasks()
    return Response(tasks)


@api_view(['POST'])
def api_cancelar_tarea(request, task_id):
    """Cancela una tarea y limpia archivos .part residuales."""
    try:
        cleaned = task_runner.cancel_task(task_id)
        return Response({
            'status': 'ok',
            'message': 'Tarea cancelada',
            'archivos_limpiados': cleaned,
        })
    except Exception as e:
        logger.error(f"Error cancelando tarea {task_id}: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===========================================================================
#  Video streaming
# ===========================================================================


@api_view(['GET'])
def api_servir_video(request, capitulo_id):
    """Sirve el archivo .mp4 con streaming por rangos."""
    try:
        capitulo = Capitulo.objects.get(id=capitulo_id)
    except Capitulo.DoesNotExist:
        raise Http404

    if not capitulo.ruta_archivo or not os.path.isfile(capitulo.ruta_archivo):
        raise Http404('Archivo no encontrado')

    file_path = capitulo.ruta_archivo
    file_stat = os.stat(file_path)

    etag_raw = f"{file_stat.st_ino}-{file_stat.st_size}-{file_stat.st_mtime}"
    etag = f'"{hashlib.md5(etag_raw.encode()).hexdigest()}"'

    if_none_match = request.META.get('HTTP_IF_NONE_MATCH', '')
    if if_none_match == etag:
        return HttpResponseNotModified()

    response = FileResponse(open(file_path, 'rb'), as_attachment=False)
    response['Content-Type'] = 'video/mp4'
    response['Content-Length'] = file_stat.st_size
    response['Accept-Ranges'] = 'bytes'
    response['ETag'] = etag
    response['Cache-Control'] = 'public, max-age=86400'
    response['Last-Modified'] = http_date(file_stat.st_mtime)
    response['Content-Disposition'] = f'inline; filename="{capitulo.nombre_archivo}"'
    return response


# ===========================================================================
#  Validacion y reparacion de archivos corruptos
# ===========================================================================


@api_view(['GET'])
def api_verificar_archivo(request, capitulo_id):
    """Verifica si el archivo de un capitulo existe y es un MP4 valido."""
    try:
        capitulo = Capitulo.objects.get(id=capitulo_id)
    except Capitulo.DoesNotExist:
        return Response({'error': 'Capitulo no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    if not capitulo.ruta_archivo or not os.path.isfile(capitulo.ruta_archivo):
        return Response({
            'status': 'no_file',
            'valido': False,
            'mensaje': 'No hay archivo descargado',
        })

    from .tasks import _validar_mp4
    valido, razon = _validar_mp4(Path(capitulo.ruta_archivo))
    file_size = os.path.getsize(capitulo.ruta_archivo)

    return Response({
        'status': 'ok' if valido else 'corrupto',
        'valido': valido,
        'mensaje': razon if not valido else 'Archivo valido',
        'tamano': file_size,
        'tamano_str': f'{file_size / (1024*1024):.1f} MB' if file_size > 0 else '0 B',
    })


@api_view(['POST'])
def api_reparar_capitulo(request, capitulo_id):
    """Limpia un archivo corrupto y lo vuelve a descargar."""
    try:
        capitulo = Capitulo.objects.get(id=capitulo_id)
    except Capitulo.DoesNotExist:
        return Response({'error': 'Capitulo no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    # Si existe archivo, validarlo primero
    if capitulo.ruta_archivo and os.path.isfile(capitulo.ruta_archivo):
        from .tasks import _validar_mp4
        valido, razon = _validar_mp4(Path(capitulo.ruta_archivo))
        if valido:
            return Response({
                'status': 'ok',
                'mensaje': 'El archivo ya es valido, no necesita reparacion',
                'skip': True,
            })

        # Eliminar archivo corrupto
        try:
            os.remove(capitulo.ruta_archivo)
        except OSError as e:
            logger.error(f"Error eliminando archivo corrupto {capitulo.ruta_archivo}: {e}")

    # Limpiar ruta en BD para que se considere no descargado
    capitulo.ruta_archivo = None
    capitulo.save(update_fields=['ruta_archivo'])

    # Iniciar nueva descarga
    task_id = task_runner.enqueue_download(capitulo_id)
    return Response({
        'status': 'reparando',
        'mensaje': f'Reparando {capitulo.nombre_archivo} — descarga reiniciada',
        'task_id': task_id,
        'capitulo_id': capitulo.id,
        'numero': capitulo.numero,
    })


# ===========================================================================
#  Ultimos episodios (trending)
# ===========================================================================


@api_view(['GET'])
def api_ultimos_episodios(request):
    """Devuelve los ultimos episodios en tendencia de JKanime.

    Enriquece los datos del scraping:
    - Si la serie no existe en BD, la crea (con portada del CDN).
    - Reemplaza la imagen por la portada local si ya existia.
    - Crea el capitulo en BD si no existe.
    """
    try:
        s = get_scraper("jkanime")
        trending = s.get_trending()

        # Precargar series de jkanime existentes en BD (slug -> serie)
        series_bd = {
            serie.slug: serie
            for serie in Serie.objects.filter(fuente="jkanime").prefetch_related("capitulos")
        }

        for ep in trending:
            url = ep.get("url", "")
            parts = url.rstrip("/").split("/")
            slug = parts[3] if len(parts) >= 4 else ""

            serie = series_bd.get(slug)
            if not serie and slug:
                # --- Crear serie nueva (patron de _run_verificar) ---
                serie_url = f"{s.BASE_URL}/{slug}/"
                serie = Serie(
                    nombre=ep.get("nombre", slug.replace("-", " ").title()),
                    url=serie_url,
                    slug=slug,
                    fuente="jkanime",
                )
                # Intentar portada del CDN
                cdn_url = f"https://cdn.jkdesa.com/assets/images/animes/image/{slug}.jpg"
                portada_ok = False
                try:
                    resp = requests.get(cdn_url, timeout=15)
                    if resp.status_code == 200:
                        img = PILImage.open(BytesIO(resp.content))
                        buf = BytesIO()
                        img.save(buf, format="JPEG")
                        safe_name = slug[:50]
                        serie.portada.save(
                            f"{safe_name}.jpg", ContentFile(buf.getvalue()), save=False
                        )
                        portada_ok = True
                except Exception as e:
                    logger.warning(f"Error descargando portada CDN para {slug}: {e}")
                # Fallback: portada del scraping
                if not portada_ok and ep.get("imagen"):
                    try:
                        resp = requests.get(ep["imagen"], timeout=15)
                        if resp.status_code == 200:
                            img = PILImage.open(BytesIO(resp.content))
                            buf = BytesIO()
                            img.save(buf, format="JPEG")
                            safe_name = slug[:50]
                            serie.portada.save(
                                f"{safe_name}.jpg", ContentFile(buf.getvalue()), save=False
                            )
                    except Exception as e:
                        logger.warning(f"Error descargando portada scraping para {slug}: {e}")
                serie.save()
                series_bd[slug] = serie

            if serie:
                # Reemplazar imagen scraping por portada local
                if serie.portada:
                    ep["imagen"] = request.build_absolute_uri(serie.portada.url)
                ep["serie_id"] = serie.id

                # Validar si el episodio existe en BD, si no -> crearlo
                ep_num_str = ep.get("episodio", "")
                capitulo = None
                ep_num = None

                # Intentar desde el badge primero
                if ep_num_str:
                    try:
                        ep_num = int(ep_num_str)
                    except (ValueError, TypeError):
                        ep_num = None

                # Fallback: extraer numero desde la URL (OVAs no ponen numero en el badge)
                if ep_num is None:
                    url_parts = url.rstrip("/").split("/")
                    last_segment = url_parts[-1] if len(url_parts) >= 5 else ""
                    try:
                        ep_num = int(last_segment)
                    except (ValueError, TypeError):
                        ep_num = None

                if ep_num is not None:
                    capitulo = serie.capitulos.filter(numero=ep_num).first()
                    if not capitulo:
                        capitulo = Capitulo.objects.create(
                            serie=serie,
                            numero=ep_num,
                            url_fuente=url,
                        )
                ep["capitulo_id"] = capitulo.id if capitulo else None
                ep["archivo_existe"] = capitulo.archivo_existe if capitulo else False
            else:
                ep["serie_id"] = None

        return Response({
            "nombre": "Últimos episodios",
            "episodios": trending,
            "total": len(trending),
        })
    except Exception as e:
        logger.error(f"Error obteniendo ultimos episodios: {e}")
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
