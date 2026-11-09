"""
REST API views for jkanime_vue.

Tareas en background via threading (task_runner) en vez de Celery + Redis.
"""

import glob
import hashlib
import logging
import os
import re
import shutil
import time
from io import BytesIO
from pathlib import Path

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Prefetch
from django.http import (
    FileResponse,
    Http404,
    HttpResponse,
    HttpResponseNotModified,
    StreamingHttpResponse,
)
from django.utils.dateparse import parse_datetime
from django.utils.http import http_date
from PIL import Image as PILImage
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .fuente import actualizar_estado_serie
from .paths import serie_download_dir
from .scrapers import get_scraper
from .trending import sincronizar_trending
from . import task_runner
from .models import Capitulo, Serie
from .serializers import (
    CapituloAdminSerializer,
    CapituloDetailSerializer,
    CapituloSerializer,
    SerieAdminSerializer,
    SerieDetailSerializer,
    SerieListSerializer,
)

logger = logging.getLogger(__name__)


# ===========================================================================
#  Series
# ===========================================================================

@api_view(['GET'])
def api_series_favoritos(request):
    """Lista series favoritas, opcionalmente filtradas por estado, dia de emision o letra inicial.

    Lectura pura de BD: la revalidacion de estado/dia_emision la hace la tarea
    en background `verificar-estados`, nunca este request.
    """
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


def _borrar_archivos_serie(serie):
    """Borra de disco los archivos de capitulos y la portada de una serie.

    Returns:
        list[str]: errores de borrado (vacio si no hubo).
    """
    errores = []
    for cap in serie.capitulos.all():
        if cap.ruta_archivo and os.path.isfile(cap.ruta_archivo):
            try:
                os.remove(cap.ruta_archivo)
            except OSError as e:
                errores.append(f'Error eliminando {cap.ruta_archivo}: {e}')

    if serie.portada and os.path.isfile(serie.portada.path):
        try:
            serie.portada.delete(save=False)
        except OSError as e:
            errores.append(f'Error eliminando portada: {e}')

    # Eliminar la carpeta de descargas de la serie y cualquier archivo restante (.part, etc.)
    serie_dir = serie_download_dir(serie.slug, serie.fuente)
    if serie_dir.exists() and serie_dir.is_dir():
        try:
            shutil.rmtree(serie_dir)
        except OSError as e:
            errores.append(f'Error eliminando carpeta {serie_dir}: {e}')

    return errores


@api_view(['DELETE'])
def api_eliminar_serie(request, serie_id):
    """Elimina una serie, sus capitulos y archivos del disco."""
    try:
        serie = Serie.objects.prefetch_related('capitulos').get(id=serie_id)
    except Serie.DoesNotExist:
        return Response({'error': 'Serie no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    delete_errors = _borrar_archivos_serie(serie)

    serie.delete()

    if delete_errors:
        return Response({
            'mensaje': 'Serie eliminada con algunos errores',
            'errores': delete_errors,
        }, status=status.HTTP_200_OK)

    return Response({'mensaje': 'Serie eliminada correctamente'})


_SERIE_ORDENES = {'nombre', '-nombre', 'anio', '-anio', 'created_at', '-created_at'}


@api_view(['GET', 'POST'])
def api_series_list(request):
    """Lista de series (GET) y creacion (POST). Filtros via query params."""
    if request.method == 'POST':
        serializer = SerieAdminSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    series = Serie.objects.prefetch_related('capitulos')

    search = request.query_params.get('search', '').strip()
    if search:
        series = series.filter(nombre__icontains=search)
    estado = request.query_params.get('estado', '').strip()
    if estado:
        series = series.filter(estado=estado)
    dia = request.query_params.get('dia', '').strip()
    if dia:
        series = series.filter(dia_emision=dia)
    fuente = request.query_params.get('fuente', '').strip()
    if fuente:
        series = series.filter(fuente=fuente)
    favorito = request.query_params.get('favorito', '').strip().lower()
    if favorito in ('true', 'false'):
        series = series.filter(favorito=favorito == 'true')
    orden = request.query_params.get('orden', '').strip()
    if orden in _SERIE_ORDENES:
        series = series.order_by(orden)

    serializer = SerieAdminSerializer(series, many=True, context={'request': request})
    return Response({'results': serializer.data})


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def api_serie_detail(request, serie_id):
    """Detalle de una serie. PUT/PATCH actualizan, DELETE elimina serie + archivos."""
    try:
        serie = (
            Serie.objects
            .prefetch_related(
                Prefetch('capitulos', queryset=Capitulo.objects.select_related('serie'))
            )
            .get(id=serie_id)
        )
    except Serie.DoesNotExist:
        return Response({'error': 'Serie no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'DELETE':
        _borrar_archivos_serie(serie)
        serie.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    if request.method in ('PUT', 'PATCH'):
        serializer = SerieAdminSerializer(
            serie,
            data=request.data,
            partial=request.method == 'PATCH',
            context={'request': request},
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

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
        actualizar_estado_serie(serie)

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


@api_view(['GET', 'POST'])
def api_capitulos_list(request):
    """Lista de capitulos (GET) y creacion (POST). Filtro opcional por serie."""
    if request.method == 'POST':
        serializer = CapituloAdminSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    capitulos = Capitulo.objects.select_related('serie')
    serie_id = request.query_params.get('serie', '').strip()
    if serie_id:
        capitulos = capitulos.filter(serie_id=serie_id)
    capitulos = capitulos.order_by('serie', 'numero')

    serializer = CapituloAdminSerializer(capitulos, many=True)
    return Response({'results': serializer.data})


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def api_capitulo_detail(request, capitulo_id):
    """Detalle de un capitulo. PUT/PATCH actualizan, DELETE borra registro + archivo."""
    try:
        cap = Capitulo.objects.select_related('serie').get(id=capitulo_id)
    except Capitulo.DoesNotExist:
        return Response({'error': 'Capitulo no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'DELETE':
        if cap.ruta_archivo and os.path.isfile(cap.ruta_archivo):
            try:
                os.remove(cap.ruta_archivo)
            except OSError as e:
                logger.error(f"Error eliminando archivo {cap.ruta_archivo}: {e}")
        # Limpiar la carpeta del capitulo si quedo vacia (best effort)
        if cap.ruta_archivo:
            try:
                parent = Path(cap.ruta_archivo).parent
                if parent.exists() and parent.is_dir():
                    parent.rmdir()
            except OSError:
                pass
        cap.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    if request.method in ('PUT', 'PATCH'):
        serializer = CapituloAdminSerializer(cap, data=request.data, partial=request.method == 'PATCH')
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

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

    ruta_existente = capitulo.ruta_archivo_real
    if ruta_existente:
        # Validar que no este corrupto antes de saltar
        from .tasks import _validar_mp4
        valido, razon = _validar_mp4(Path(ruta_existente))
        if valido:
            # Auto-sanado: si la ruta en BD estaba vacia pero el archivo estaba
            # en la ruta canonica, se persiste para no volver a resolverla.
            if capitulo.ruta_archivo != ruta_existente:
                capitulo.ruta_archivo = ruta_existente
                capitulo.save(update_fields=['ruta_archivo'])
            return Response({'status': 'ok', 'message': 'Ya existe', 'skip': True})
        # Archivo corrupto: eliminar y descargar de nuevo
        logger.warning(f"Archivo corrupto detectado en {capitulo.nombre_archivo}: {razon}")
        try:
            os.remove(ruta_existente)
        except OSError as e:
            logger.error(f"No se pudo eliminar {ruta_existente}: {e}")
        # Si el borrado fallo (archivo bloqueado) la ruta se conserva: la
        # descarga igual lo sobreescribe porque usa os.replace.
        if not os.path.isfile(ruta_existente):
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

    # OJO: `archivo_existe` solo dice "hay algo en disco con ese nombre". Un
    # archivo puede existir y estar corrupto (los stubs de ~1.6 KB con la landing
    # de Mega guardada como .mp4). Eso NO es una descarga valida. Filtrar por
    # `not c.archivo_existe` dejaba esos capitulos afuera para siempre: el boton
    # individual respondia "Ya existe" y este endpoint "No hay capitulos para
    # descargar", asi que nunca se reparaban. Validamos igual que ese flujo.
    from .tasks import _validar_mp4

    # OJO: `ruta_archivo_real` devuelve `str | None` (no un Path), por eso hay que
    # envolverlo: `_validar_mp4` llama a `.exists()` sobre el argumento.
    from .tasks import _validar_mp4

    capitulos_faltantes = [
        c for c in Capitulo.objects.select_related('serie').filter(serie=serie)
        if c.ruta_archivo_real is None or not _validar_mp4(Path(c.ruta_archivo_real))[0]
    ]
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
#  Verificacion de estados (solo series en emision)
# ===========================================================================


@api_view(['GET', 'POST'])
def api_verificar_estados(request):
    """POST: lanza la revalidacion de estado en background. GET: estado de la tarea activa.

    A diferencia de `api_verificar_series`, esta tarea NO scrapea el catalogo
    completo: solo revalida estado/dia_emision de las series que ya estan en
    `en_emision`, respetando el cooldown de REFRESH_ESTADO_HORAS.
    """
    from .task_runner import _estados_task_id

    if request.method == 'GET':
        tid = _estados_task_id
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
    tid = _estados_task_id
    if tid:
        task = task_runner.get_task(tid)
        if task and task.get('state') in ('PENDING', 'PROGRESS'):
            return Response({
                'status': 'already_running',
                'task_id': tid,
                **{k: v for k, v in task.items() if k not in ('task_id',)},
            })

    new_tid = task_runner.enqueue_verificar_estados()
    if not new_tid:
        return Response({'status': 'already_running'})
    return Response({'status': 'started', 'task_id': new_tid})


# ===========================================================================
#  Verificacion de trending (episodios nuevos)
# ===========================================================================


@api_view(['GET', 'POST'])
def api_verificar_trending(request):
    """POST: lanza el chequeo de episodios nuevos en background. GET: estado.

    Corre el MISMO `trending.sincronizar_trending` que usa
    `api_ultimos_episodios`, pero con scrape forzado: el endpoint lee lo que la
    cache de 30 min tiene, y esta tarea existe justamente para no depender de
    ese TTL. El frontend la dispara cada hora y con el boton manual.

    El GET no lleva `Cache-Control: no-store` por capricho: el poll cada 2s
    repetiria la respuesta si un proxy la cacheara, y `nuevos` volveria a
    disparar el reload de la lista.
    """
    from .task_runner import _trending_task_id

    if request.method == 'GET':
        tid = _trending_task_id
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
    tid = _trending_task_id
    if tid:
        task = task_runner.get_task(tid)
        if task and task.get('state') in ('PENDING', 'PROGRESS'):
            return Response({
                'status': 'already_running',
                'task_id': tid,
                **{k: v for k, v in task.items() if k not in ('task_id',)},
            })

    new_tid = task_runner.enqueue_verificar_trending()
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
    elif re.search(r'hentaid\.tv', url):
        fuente = 'hentaidtv'
        # En hentaid.tv la serie vive bajo /ver/<slug>
        match = re.search(r'hentaid\.tv/ver/([^/\s?#]+)', url)
        if match:
            slug = match.group(1)
    elif re.search(r'animeflv\.[a-z]+', url, re.IGNORECASE):
        fuente = 'animeflv'
        # La URL canonica de la serie es /anime/<slug>. Tambien se acepta una
        # URL de episodio (/ver/...): ahi el slug se resuelve desde el
        # breadcrumb dentro del scraper, por eso no siempre sale de la URL.
        match = re.search(r'animeflv\.[a-z]+/anime/([^/\s?#]+)', url, re.IGNORECASE)
        if match:
            slug = match.group(1)
    elif re.search(r'youtube\.com/', url, re.IGNORECASE) or re.search(r'youtu\.be/', url, re.IGNORECASE):
        # YouTube: playlist (serie) o video individual (1 capítulo)
        fuente = 'youtube'
        # Preferimos playlist si viene en la URL (watch?v=...&list=... o playlist?list=...)
        playlist_match = re.search(r'[?&]list=([a-zA-Z0-9_-]+)', url)
        if playlist_match:
            slug = f"youtube-{playlist_match.group(1)}"
        else:
            vid_match = re.search(
                r'(?:v=|youtu\.be/|/embed/|/shorts/|/live/)([a-zA-Z0-9_-]{11})',
                url,
            )
            if vid_match:
                slug = f"youtube-{vid_match.group(1)}"
            else:
                return Response({
                    'error': 'No se pudo extraer el ID de video o playlist de la URL de YouTube'
                }, status=status.HTTP_400_BAD_REQUEST)
    else:
        return Response({
            'error': 'URL no válida. Debe ser de jkanime.net, latanime.org, animeflv, hentaid.tv o YouTube'
        }, status=status.HTTP_400_BAD_REQUEST)

    if not slug and fuente != 'animeflv':
        return Response({
            'error': 'No se pudo extraer el slug de la URL'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Verificar si ya existe por slug (namespace por fuente para evitar colisiones)
    if slug and Serie.objects.filter(slug=slug, fuente=fuente).exists():
        serie = Serie.objects.get(slug=slug, fuente=fuente)
        # Al (re)agregarla por URL se marca como favorita de inmediato.
        if not serie.favorito:
            serie.favorito = True
            serie.save(update_fields=['favorito'])
        return Response({
            'status': 'ok',
            'message': f'"{serie.nombre}" ya está en la lista (marcada como favorita)',
            'serie_id': serie.id,
            'existing': True,
            'favorito': True,
        })

    s = get_scraper(fuente)
    info = s.get_series_info(url)
    if not info:
        return Response({
            'error': 'No se pudo obtener info de la serie. Verifica la URL.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Cuando la URL era de episodio, el slug recien se conoce ahora: se repite
    # el chequeo de duplicados para no crear una segunda serie de la misma
    # fuente.
    if not slug:
        existente = Serie.objects.filter(slug=info['slug'], fuente=fuente).first()
        if existente:
            if not existente.favorito:
                existente.favorito = True
                existente.save(update_fields=['favorito'])
            return Response({
                'status': 'ok',
                'message': f'"{existente.nombre}" ya está en la lista (marcada como favorita)',
                'serie_id': existente.id,
                'existing': True,
                'favorito': True,
            })

    serie = Serie(
        nombre=info['nombre'],
        # Los scrapers que ya exponen una URL canonica (p. ej. YouTube, donde
        # no hay SERIE_URL_TEMPLATE valido para un video suelto) la devuelven
        # en `info['url']`; el resto sigue usando el template del scraper.
        url=info.get('url') or s.SERIE_URL_TEMPLATE.format(base=s.BASE_URL, slug=info['slug']),
        slug=info['slug'],
        estado=info.get('estado', 'desconocido'),
        fuente=fuente,
        favorito=True,
    )

    if info.get('cover_url'):
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
        'message': f'Serie "{info["nombre"]}" agregada con {len(eps)} capítulos (favorita)',
        'serie_id': serie.id,
        'fuente': fuente,
        'capitulos': len(eps),
        'favorito': True,
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


def _parse_byte_range(range_header, file_size):
    """Parsea el header `Range` de una sola peticion de bytes.

    Devuelve la tupla (start, end) inclusiva, la cadena 'unsatisfiable' si el
    rango es sintacticamente valido pero cae fuera del archivo, o None si no
    hay rango aplicable (entonces se sirve el archivo completo).
    """
    if not range_header or not range_header.lower().startswith('bytes='):
        return None

    # Un <video> envia un unico rango; se ignora el resto si hay varios.
    spec = range_header[len('bytes='):].split(',')[0].strip()
    if '-' not in spec:
        return None

    start_s, end_s = spec.split('-', 1)
    try:
        if start_s == '':
            # Forma sufijo: bytes=-N (ultimos N bytes).
            n = int(end_s)
            if n <= 0:
                return 'unsatisfiable'
            start = max(0, file_size - n)
            end = file_size - 1
        else:
            start = int(start_s)
            end = int(end_s) if end_s != '' else file_size - 1
    except ValueError:
        return None

    if start >= file_size or start > end:
        return 'unsatisfiable'
    end = min(end, file_size - 1)
    return (start, end)


def _file_range_iterator(file_path, start, length, chunk_size=262144):
    """Genera exactamente `length` bytes del archivo desde `start`, en bloques."""
    remaining = length
    with open(file_path, 'rb') as fh:
        fh.seek(start)
        while remaining > 0:
            data = fh.read(min(chunk_size, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


@api_view(['GET'])
def api_servir_video(request, capitulo_id):
    """Sirve el .mp4 con soporte real de HTTP Range (206 Partial Content).

    Sin esto el <video> pide un rango (seek o buffer) y recibe el archivo
    entero con 200, lo que provoca rebuffering constante y conexiones cortadas.
    """
    try:
        capitulo = Capitulo.objects.get(id=capitulo_id)
    except Capitulo.DoesNotExist:
        raise Http404

    file_path = capitulo.ruta_archivo_real
    if not file_path:
        raise Http404('Archivo no encontrado')

    file_stat = os.stat(file_path)
    file_size = file_stat.st_size

    etag_raw = f"{file_stat.st_ino}-{file_size}-{file_stat.st_mtime}"
    etag = f'"{hashlib.md5(etag_raw.encode()).hexdigest()}"'

    if_none_match = request.META.get('HTTP_IF_NONE_MATCH', '')
    if if_none_match == etag:
        return HttpResponseNotModified()

    common_headers = {
        'Accept-Ranges': 'bytes',
        'ETag': etag,
        'Cache-Control': 'public, max-age=86400',
        'Last-Modified': http_date(file_stat.st_mtime),
        'Content-Disposition': f'inline; filename="{capitulo.nombre_archivo}"',
    }

    parsed = _parse_byte_range(request.META.get('HTTP_RANGE', ''), file_size)

    if parsed == 'unsatisfiable':
        response = HttpResponse(status=416)
        response['Content-Range'] = f'bytes */{file_size}'
        response['Accept-Ranges'] = 'bytes'
        return response

    if parsed:
        start, end = parsed
        length = end - start + 1
        response = StreamingHttpResponse(
            _file_range_iterator(file_path, start, length),
            status=206,
            content_type='video/mp4',
        )
        response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
        response['Content-Length'] = str(length)
    else:
        response = StreamingHttpResponse(
            _file_range_iterator(file_path, 0, file_size),
            content_type='video/mp4',
        )
        response['Content-Length'] = str(file_size)

    for key, value in common_headers.items():
        response[key] = value
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

    file_path = capitulo.ruta_archivo_real
    if not file_path:
        return Response({
            'status': 'no_file',
            'valido': False,
            'mensaje': 'No hay archivo descargado',
        })

    from .tasks import _validar_mp4
    valido, razon = _validar_mp4(Path(file_path))
    file_size = os.path.getsize(file_path)

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

    # Si existe archivo (en ruta_archivo o en la ruta canonica), validarlo primero
    ruta_existente = capitulo.ruta_archivo_real
    if ruta_existente:
        from .tasks import _validar_mp4
        valido, razon = _validar_mp4(Path(ruta_existente))
        if valido:
            return Response({
                'status': 'ok',
                'mensaje': 'El archivo ya es valido, no necesita reparacion',
                'skip': True,
            })

        # Eliminar archivo corrupto
        try:
            os.remove(ruta_existente)
        except OSError as e:
            logger.error(f"Error eliminando archivo corrupto {ruta_existente}: {e}")

    # Limpiar ruta en BD para que se considere no descargado.
    # Si el archivo corrupto no se pudo borrar, se conserva la ruta: la
    # re-descarga lo sobreescribe igual porque usa os.replace.
    if ruta_existente and os.path.isfile(ruta_existente):
        logger.warning(f"Archivo bloqueado, se conserva la ruta: {ruta_existente}")
    else:
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

    Toda la escritura en BD vive en `trending.sincronizar_trending`, que es la
    misma que corre la tarea en background `verificar-trending`: asi el endpoint
    y la tarea no pueden escribir distinto. Aca solo queda el armado de la
    respuesta, que es lo unico que depende de la request:

    - Reemplaza la imagen del scraping por la portada local (URL absoluta: la
      ruta que deja el modulo es relativa).
    - Embalsa el payload con la forma que el frontend ya consume.

    El scraping entra por la cache de 30 min del trending; la tarea horaria y el
    boton manual fuerzan scrape y llegan con lo mismo.
    """
    try:
        trending = get_scraper("jkanime").get_trending()
        sincronizar_trending(trending)

        for ep in trending:
            # `portada_url` es relativa y la resuelve esta capa con el host de la
            # request. Se saca del dict para que no viaje en el JSON.
            portada = ep.pop('portada_url', None)
            if portada:
                ep['imagen'] = request.build_absolute_uri(portada)

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
