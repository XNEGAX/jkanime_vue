"""
Sincronizacion del trending de JKanime contra la BD.

Modulo neutral a proposito: no importa views ni task_runner, solo models,
scrapers y django. Es el mismo criterio (y el mismo tradeoff) que `fuente.py`:
el endpoint de lectura `/api/ultimos-episodios/` y la tarea en background
`verificar-trending` necesitan EXACTAMENTE la misma escritura en BD — mismas
filas de Serie, mismos capitulos, misma portada—, y con la logica duplicada en
los dos lados una tarde el endpoint muestra un capitulo que la tarea jamas creo,
o al reves, y el "¿por que no me aparece?" no tiene respuesta. Cuando el
endpoint crecio a ~140 lineas de enriquecimiento y la tarea necesito copia, ese
era el momento de extraer.

Se importa desde `views.py` y desde `tasks.py`. Ninguno de los dos lo importa a
su vez, asi que no hay ciclo: este modulo baja a `models` + `scrapers` y nada
mas.
"""

import logging
import time
from io import BytesIO

import requests
from django.core.files.base import ContentFile
from PIL import Image as PILImage

from .fuente import SCRAPE_DELAY_SEGUNDOS
from .models import Capitulo, Serie
from .scrapers import get_scraper
# El CDN de portadas se importa desde el scraper y no se re-declara aqui. Estaba
# duplicado en los dos modulos y la copia de este modulo se comio la extension
# `.jpg`, que es obligatoria: sin ella el CDN devuelve 404 para todos los slugs y
# `_descargar_portada` caia siempre al fallback del scraping. Una sola fuente de
# verdad para la URL.
from .scrapers.jkanime import CDN_PORTADA

logger = logging.getLogger(__name__)


def sincronizar_trending(episodios: list[dict], al_progresar=None) -> dict:
    """Crea/actualiza Series y Capitulos desde una lista de trending.

    Escribe en BD lo que el trending anuncie y le falte: serie nueva con portada,
    capitulo nuevo. NO toca el estado/dia_emision de las series que ya existen:
    eso corre en la tarea `verificar-estados`, que respeta el cooldown de
    REFRESH_ESTADO_HORAS. El unico `get_series_info` que hace esta funcion es
    para las series que nacen aqui, y solo para que el registro no quede en
    'desconocido' para siempre.

    Muta los dicts de entrada para anotar `serie_id`, `capitulo_id` y
    `archivo_existe`, y deja en `portada_url` la ruta local de la portada
    cuando la hay. El llamador los necesita para armar la respuesta y volver a
    buscarlos seria una query por episodio (72 en una pasada); la ruta de portada
    va sin convertir a URL absoluta porque eso necesita el host de la request y
    esta capa no lo tiene.

    Args:
        episodios: dicts de `get_trending()`. Se pueden mutar.
        al_progresar: opcional, recibe `(indice, total, episodio, nuevos)` y
            devuelve False para abortar. Es lo que usa la tarea en background
            para reportar progreso y para ceder a una cancelacion.

    Returns:
        dict: {'nuevos': [{'serie_id', 'numero', 'nombre', 'slug', 'tab'}],
               'total': int, 'cancelado': bool}

        `nuevos` son los capitulos que ESTA corrida creo. `Capitulo` tiene
        unique_together (serie, numero) y ninguna columna de timestamp, asi que
        "la fila se creo" es el proxy fiable de "episodio recien descubierto" y
        no hace falta migracion para saberlo. `total` es la cantidad de
        episodios del trending, no de capitulos: es el denominador del progreso.
    """
    total = len(episodios)
    if not total:
        return {'nuevos': [], 'total': 0, 'cancelado': False}

    scraper = get_scraper('jkanime')

    series_bd = {
        serie.slug: serie
        for serie in Serie.objects.filter(fuente='jkanime')
    }

    # El trending trae dos episodios de la misma serie con distinta pestana, asi
    # que se resuelve el numero y el slug de TODO primero y recien despues se
    # escribe: la serie se crea una vez y se reutiliza.
    resueltos = []
    for ep in episodios:
        url = ep.get('url', '')
        slug = _slug_de_url(url)
        resueltos.append((ep, slug, _numero_de_episodio(ep, url)))

    for slug, ep in _pendientes_crear(resueltos, series_bd).items():
        serie = _crear_serie(scraper, slug, ep)
        series_bd[slug] = serie

    # Una sola query para todos los capitulos. El camino anterior iba a
    # `serie.capitulos.filter(numero=...)` por episodio, o sea una query por item
    # del trending; con el trending real (72 items) eso son 72 SELECTs por visita
    # a la pantalla de favoritos.
    numeros = {num for _, _, num in resueltos if num is not None}
    existentes = {}
    if numeros:
        for cap in Capitulo.objects.filter(
            serie__in=series_bd.values(), numero__in=numeros
        ):
            existentes[(cap.serie_id, cap.numero)] = cap

    nuevos = []
    for idx, (ep, slug, numero) in enumerate(resueltos, start=1):
        serie = series_bd.get(slug)
        if not serie:
            # Slug ilegible o serie de otra fuente: se deja el episodio tal cual
            # vino, sin serie_id. La vista lo muestra igual.
            ep['serie_id'] = None
            ep['capitulo_id'] = None
            ep['archivo_existe'] = False
            continue

        if serie.portada:
            ep['portada_url'] = serie.portada.url

        capitulo = existentes.get((serie.id, numero)) if numero is not None else None
        if numero is not None and capitulo is None:
            # get_or_create y no un filter+create: `unique_together` mas dos
            # requests concurrentes (el endpoint y la tarea) es una carrera, y el
            # INSERT perdedor revienta con IntegrityError. get_or_create resuelve
            # la carrera y de paso `created` dice si es nuevo de verdad.
            capitulo, creado = Capitulo.objects.get_or_create(
                serie=serie,
                numero=numero,
                defaults={'url_fuente': ep.get('url', '')},
            )
            existentes[(serie.id, numero)] = capitulo
            if creado:
                nuevos.append({
                    'serie_id': serie.id,
                    'numero': numero,
                    'nombre': ep.get('nombre', ''),
                    'slug': slug,
                    'tab': ep.get('tab', ''),
                })

        ep['serie_id'] = serie.id
        ep['capitulo_id'] = capitulo.id if capitulo else None
        ep['archivo_existe'] = capitulo.archivo_existe if capitulo else False

        if al_progresar is not None and not al_progresar(idx, total, ep, nuevos):
            return {'nuevos': nuevos, 'total': total, 'cancelado': True}

    return {'nuevos': nuevos, 'total': total, 'cancelado': False}


def _pendientes_crear(resueltos, series_bd) -> dict:
    """Slugs del trending que todavia no estan en BD, con un episodio de muestra.

    Un dict y no una lista porque el trending trae varios episodios de la misma
    serie y la fila se crea una sola vez. El primer episodio que aparece manda
    el nombre y la imagen de portada.
    """
    pendientes = {}
    for ep, slug, _ in resueltos:
        if slug and slug not in series_bd and slug not in pendientes:
            pendientes[slug] = ep
    return pendientes


def _crear_serie(scraper, slug: str, ep: dict) -> Serie:
    """Crea la Serie del slug con estado/dia_emision reales de la fuente."""
    try:
        info = scraper.get_series_info(f"{scraper.BASE_URL}/{slug}/")
    except Exception as e:
        logger.warning(f"Error obteniendo info de {slug} para el trending: {e}")
        info = None
    finally:
        # Pausa tambien cuando falla: el pacing protege a la fuente, y este
        # bucle puede tener que crear varias series nuevas de una.
        time.sleep(SCRAPE_DELAY_SEGUNDOS)

    serie = Serie(
        nombre=ep.get('nombre') or slug.replace('-', ' ').title(),
        url=f"{scraper.BASE_URL}/{slug}/",
        slug=slug,
        fuente='jkanime',
        estado=info.get('estado', 'desconocido') if info else 'desconocido',
        dia_emision=info.get('dia_emision', '') if info else '',
    )
    _descargar_portada(serie, slug, ep.get('imagen', ''))
    serie.save()
    return serie


def _descargar_portada(serie, slug: str, imagen_scrape: str) -> None:
    """Deja la mejor portada disponible en `serie.portada`, sin guardarla.

    Primero el CDN de jkanime y, si no responde, la imagen que trajo el propio
    scraping. Convertir a JPEG es lo que espera el resto de la app (el ImageField
    se sirve como .jpg y el nombre ya lo dice).
    """
    cdn_url = CDN_PORTADA.format(slug=slug)
    if _guardar_portada(serie, cdn_url, slug):
        return
    if imagen_scrape and imagen_scrape != cdn_url:
        _guardar_portada(serie, imagen_scrape, slug)


def _guardar_portada(serie, url: str, slug: str) -> bool:
    """Intenta guardar `url` como portada de `serie`. Devuelve si lo logro."""
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            return False
        img = PILImage.open(BytesIO(resp.content))
        buf = BytesIO()
        img.save(buf, format='JPEG')
        serie.portada.save(f"{slug[:50]}.jpg", ContentFile(buf.getvalue()), save=False)
        return True
    except Exception as e:
        logger.warning(f"Error descargando portada {url} para {slug}: {e}")
        return False


def _slug_de_url(url: str) -> str:
    """Slug de una URL de jkanime (`<base>/<slug>/<ep>/`), o '' si no se puede."""
    partes = url.rstrip('/').split('/')
    return partes[3] if len(partes) >= 4 else ''


def _numero_de_episodio(ep: dict, url: str) -> int | None:
    """Numero de episodio del trending, o None si no se puede determinar.

    Primero el badge del scraping, que las OVAs no llenan. Ahi el ultimo
    segmento de la URL, que en el formato de jkanime ES el numero. None significa
    "no crear capitulo": es preferible a inventar el numero 0 y colisionar con
    la unicidad (serie, numero).
    """
    crudo = ep.get('episodio', '')
    if crudo:
        try:
            return int(crudo)
        except (ValueError, TypeError):
            pass

    partes = url.rstrip('/').split('/')
    if len(partes) >= 5:
        try:
            return int(partes[-1])
        except (ValueError, TypeError):
            return None
    return None
