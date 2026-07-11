"""
REST API views for jkanime_vue.
"""
import os
import logging
from pathlib import Path

from django.http import FileResponse, Http404
from django.conf import settings
from django.utils.dateparse import parse_datetime
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from celery.result import AsyncResult
from celery.states import SUCCESS, FAILURE

from .models import Serie, Capitulo
from . import scraper
from .tasks import descargar_capitulo, descargar_todos, verificar_series_task
from .serializers import (
    SerieListSerializer, SerieDetailSerializer,
    CapituloSerializer, CapituloDetailSerializer,
)

logger = logging.getLogger(__name__)


@api_view(['GET'])
def api_series(request):
    """Lista todas las series, opcionalmente filtradas por busqueda."""
    search = request.query_params.get('search', '').strip()
    series = Serie.objects.all()
    if search:
        series = series.filter(nombre__icontains=search)
    serializer = SerieListSerializer(series, many=True, context={'request': request})
    return Response(serializer.data)


@api_view(['GET'])
def api_series_favoritos(request):
    """Lista solo las series marcadas como favoritas."""
    series = Serie.objects.filter(favorito=True)
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


@api_view(['GET'])
def api_serie_detail(request, serie_id):
    """Detalle de una serie con sus capitulos."""
    try:
        serie = Serie.objects.prefetch_related('capitulos').get(id=serie_id)
    except Serie.DoesNotExist:
        return Response({'error': 'Serie no encontrada'}, status=status.HTTP_404_NOT_FOUND)
    serializer = SerieDetailSerializer(serie, context={'request': request})
    return Response(serializer.data)


@api_view(['GET'])
def api_capitulos(request, serie_id):
    """Lista capitulos de una serie (scrapea JKanime para nuevos)."""
    try:
        serie = Serie.objects.get(id=serie_id)
    except Serie.DoesNotExist:
        return Response({'error': 'Serie no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    try:
        eps_jk = scraper.get_episodes_for_series(serie.slug)
        eps_locales = {c.numero for c in serie.capitulos.all()}

        nuevos = [ep for ep in eps_jk if ep['numero'] not in eps_locales]

        for ep in nuevos:
            defaults = {'url_jkanime': ep['url']}
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

        # Actualizar estado y dia de emision desde JKanime
        try:
            info = scraper.get_series_info_by_url(serie.url)
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

        capitulos = serie.capitulos.all().order_by('numero')
        serializer = CapituloSerializer(capitulos, many=True)

        return Response({
            'capitulos': serializer.data,
            'nuevos_encontrados': len(nuevos),
            'total_jk': len(eps_jk),
        })
    except Exception as e:
        logger.error(f"Error en API de capitulos para {serie.nombre}: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'POST'])
def api_verificar_series(request):
    """POST: lanza tarea Celery de verificacion. GET: devuelve estado de la tarea activa."""
    from django.core.cache import cache

    if request.method == 'GET':
        task_id = cache.get('verificacion_task_id')
        if not task_id:
            return Response({'state': 'NONE'})
        result = AsyncResult(task_id)
        if result.state == 'PENDING':
            data = {'state': 'PENDING', 'task_id': task_id, 'message': 'En cola...'}
        elif result.state == 'PROGRESS':
            meta = result.info or {}
            data = {'state': 'PROGRESS', 'task_id': task_id, **meta}
        elif result.state == SUCCESS:
            info = result.result if isinstance(result.result, dict) else {}
            data = {'state': 'SUCCESS', **info}
            cache.delete('verificacion_task_id')
        elif result.state == FAILURE:
            data = {'state': 'FAILURE', 'message': str(result.info)}
            cache.delete('verificacion_task_id')
        else:
            data = {'state': result.state, 'task_id': task_id}
        resp = Response(data)
        resp['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return resp

    # POST: lanzar tarea si no hay una activa
    task_id = cache.get('verificacion_task_id')
    if task_id:
        result = AsyncResult(task_id)
        if result.state in ('PENDING', 'PROGRESS'):
            meta = result.info or {}
            return Response({
                'status': 'already_running',
                'task_id': task_id,
                **meta,
            })

    task = verificar_series_task.delay()
    cache.set('verificacion_task_id', task.id, 3600)
    return Response({'status': 'started', 'task_id': task.id})


@api_view(['POST'])
def api_agregar_serie_url(request):
    """Agrega una serie desde una URL directa de JKanime."""
    url = request.data.get('url', '').strip()
    if not url:
        return Response({'error': 'Se requiere una URL'}, status=status.HTTP_400_BAD_REQUEST)

    slug = None
    import re as _re
    match = _re.search(r'jkanime\.net/([^/\s]+)', url)
    if match:
        slug = match.group(1)
    if not slug:
        return Response({'error': 'URL no valida. Debe ser de jkanime.net'}, status=status.HTTP_400_BAD_REQUEST)

    if Serie.objects.filter(slug=slug).exists():
        serie = Serie.objects.get(slug=slug)
        return Response({
            'status': 'ok',
            'message': f'"{serie.nombre}" ya esta en la lista',
            'serie_id': serie.id,
            'existing': True,
        })

    info = scraper.get_series_info_by_url(url)
    if not info:
        return Response({'error': 'No se pudo obtener info de la serie. Verifica la URL.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    serie = Serie(
        nombre=info['nombre'],
        url=f"{scraper.BASE_URL}/{info['slug']}/",
        slug=info['slug'],
        estado=info.get('estado', 'desconocido'),
    )

    if info.get('cover_url'):
        try:
            import requests
            from io import BytesIO
            from PIL import Image as PILImage
            from django.core.files.base import ContentFile
            resp = requests.get(info['cover_url'], timeout=30)
            if resp.status_code == 200:
                img = PILImage.open(BytesIO(resp.content))
                buf = BytesIO()
                img.save(buf, format='JPEG')
                serie.portada.save(f"{info['slug'][:50]}.jpg", ContentFile(buf.getvalue()), save=False)
        except Exception as e:
            logger.warning(f"Error descargando portada: {e}")

    serie.save()

    eps = scraper.get_episodes_for_series(info['slug'])
    for ep in eps:
        defaults = {'url_jkanime': ep['url']}
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
        'message': f'Serie "{info["nombre"]}" agregada con {len(eps)} capitulos',
        'serie_id': serie.id,
        'capitulos': len(eps),
    })


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
def api_descargar_capitulo(request, capitulo_id):
    """Inicia descarga de un capitulo via Celery."""
    try:
        capitulo = Capitulo.objects.get(id=capitulo_id)
    except Capitulo.DoesNotExist:
        return Response({'error': 'Capitulo no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    if capitulo.archivo_existe:
        return Response({'status': 'ok', 'message': 'Ya existe', 'skip': True})

    try:
        task = descargar_capitulo.delay(capitulo_id)
        return Response({
            'status': 'ok',
            'message': f'Descarga iniciada: {capitulo.nombre_archivo}',
            'task_id': task.id,
        })
    except Exception as e:
        logger.error(f"Error lanzando tarea: {e}")
        return Response({'error': f'Error conectando con Celery: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def api_descargar_todos(request, serie_id):
    """Lanza una tarea individual de Celery por cada capitulo faltante."""
    try:
        serie = Serie.objects.get(id=serie_id)
    except Serie.DoesNotExist:
        return Response({'error': 'Serie no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    capitulos_faltantes = [c for c in serie.capitulos.all() if not c.archivo_existe]
    if not capitulos_faltantes:
        return Response({'status': 'ok', 'message': 'No hay capitulos para descargar'})

    tasks = []
    for cap in capitulos_faltantes:
        try:
            task = descargar_capitulo.delay(cap.id)
            tasks.append({
                'task_id': task.id,
                'capitulo_id': cap.id,
                'numero': cap.numero,
                'nombre_archivo': cap.nombre_archivo,
            })
        except Exception as e:
            logger.error(f"Error lanzando tarea para ep {cap.numero}: {e}")

    return Response({
        'status': 'ok',
        'message': f'Descargas iniciadas: {len(tasks)}/{len(capitulos_faltantes)}',
        'tasks': tasks,
        'total': len(tasks),
    })


@api_view(['GET'])
def api_estado_tarea(request, task_id):
    """Estado y progreso de una tarea Celery."""
    try:
        result = AsyncResult(task_id)

        if result.state == 'PENDING':
            data = {'state': 'PENDING', 'message': 'En cola...'}
        elif result.state == 'PROGRESS':
            meta = result.info or {}
            data = {'state': 'PROGRESS', **meta}
        elif result.state == SUCCESS:
            info = result.result if isinstance(result.result, dict) else {}
            data = {'state': 'SUCCESS', **info}
        elif result.state == FAILURE:
            data = {'state': 'FAILURE', 'message': str(result.info)}
        else:
            data = {'state': result.state}

        resp = Response(data)
        resp['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        resp['Pragma'] = 'no-cache'
        resp['Expires'] = '0'
        return resp
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def api_cancelar_tarea(request, task_id):
    """Cancela una tarea Celery y limpia archivos residuales."""
    from celery import Celery
    from django.conf import settings as _settings
    import glob as _glob

    try:
        result = AsyncResult(task_id)

        # Revoke the task
        app = Celery('jkanime_vue')
        app.config_from_object(_settings, namespace='CELERY')
        app.control.revoke(task_id, terminate=True)

        # Clean up .part files if we have the info
        meta = {}
        if result.state == 'PROGRESS':
            meta = result.info or {}
        elif result.state == 'PENDING':
            # Try to get meta from Redis directly
            import json as _json
            import redis as _redis
            r = _redis.Redis.from_url(_settings.CELERY_RESULT_BACKEND)
            raw = r.get(f'celery-task-meta-{task_id}')
            if raw:
                stored = _json.loads(raw)
                meta = stored.get('result') or {}

        slug = meta.get('slug', '')
        capitulo = meta.get('capitulo', '')

        cleaned = 0
        if slug and capitulo:
            download_dir = Path(_settings.DOWNLOAD_DIR)
            pattern = str(download_dir / slug / f"{Path(capitulo).stem}*.part")
            for part_file in _glob.glob(pattern):
                try:
                    Path(part_file).unlink()
                    cleaned += 1
                except OSError:
                    pass

        # Remove from Redis
        import redis as _redis
        r = _redis.Redis.from_url(_settings.CELERY_RESULT_BACKEND)
        r.delete(f'celery-task-meta-{task_id}')

        return Response({
            'status': 'ok',
            'message': 'Tarea cancelada',
            'archivos_limpiados': cleaned,
        })
    except Exception as e:
        logger.error(f"Error cancelando tarea {task_id}: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def api_tareas_activas(request):
    """Devuelve tareas realmente ejecutándose, usando Celery inspect."""
    import json as _json
    import redis as _redis
    from celery import current_app as celery_app

    try:
        real_ids = set()
        i = celery_app.control.inspect(timeout=2.0)
        for task_map in (i.active() or {}, i.reserved() or {}):
            for worker_tasks in task_map.values():
                for t in worker_tasks:
                    real_ids.add(t.get('id', ''))

        if not real_ids:
            return Response([])

        r = _redis.Redis.from_url(settings.CELERY_RESULT_BACKEND)
        activas = []
        for task_id in real_ids:
            raw = r.get(f'celery-task-meta-{task_id}')
            if not raw:
                continue
            data = _json.loads(raw)
            state = data.get('status', '')
            if state not in ('PENDING', 'PROGRESS'):
                continue

            result = data.get('result') or {}
            activas.append({
                'task_id': task_id,
                'state': state,
                'capitulo': result.get('capitulo', ''),
                'numero': result.get('numero', 0),
                'serie': result.get('serie', ''),
                'fase': result.get('fase', ''),
                'servidor': result.get('servidor', ''),
                'descargado': result.get('descargado', 0),
                'total': result.get('total', 0),
                'descargado_str': result.get('descargado_str', '0 B'),
                'total_str': result.get('total_str', '0 B'),
                'porcentaje': result.get('porcentaje', 0),
            })
        return Response(activas)
    except Exception as e:
        logger.error(f"Error obteniendo tareas activas: {e}")
        return Response([])


@api_view(['GET'])
def api_servir_video(request, capitulo_id):
    """Sirve el archivo .mp4 con headers de cache."""
    import hashlib
    import time

    try:
        capitulo = Capitulo.objects.get(id=capitulo_id)
    except Capitulo.DoesNotExist:
        raise Http404

    if not capitulo.ruta_archivo or not os.path.isfile(capitulo.ruta_archivo):
        raise Http404('Archivo no encontrado')

    file_path = capitulo.ruta_archivo
    file_stat = os.stat(file_path)
    file_size = file_stat.st_size
    last_modified = time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime(file_stat.st_mtime))

    # ETag basado en inode + size + mtime
    etag_raw = f"{file_stat.st_ino}-{file_size}-{file_stat.st_mtime}"
    etag = f'"{hashlib.md5(etag_raw.encode()).hexdigest()}"'

    if_none_match = request.META.get('HTTP_IF_NONE_MATCH', '')
    if if_none_match == etag:
        from django.http import HttpResponseNotModified
        return HttpResponseNotModified()

    range_header = request.META.get('HTTP_RANGE')
    if range_header:
        byte_start = 0
        byte_end = file_size - 1
        range_match = __import__('re').match(r'bytes=(\d+)-(\d*)', range_header)
        if range_match:
            byte_start = int(range_match.group(1))
            if range_match.group(2):
                byte_end = int(range_match.group(2))

        content_length = byte_end - byte_start + 1
        response = FileResponse(
            open(file_path, 'rb'),
            content_type='video/mp4',
            status=206,
        )
        response['Content-Range'] = f'bytes {byte_start}-{byte_end}/{file_size}'
        response['Content-Length'] = str(content_length)
        response['Accept-Ranges'] = 'bytes'
    else:
        response = FileResponse(
            open(file_path, 'rb'),
            content_type='video/mp4',
        )
        response['Accept-Ranges'] = 'bytes'

    response['ETag'] = etag
    response['Cache-Control'] = 'public, max-age=86400'
    response['Last-Modified'] = last_modified
    response['Content-Disposition'] = f'inline; filename="{capitulo.nombre_archivo}"'
    return response
