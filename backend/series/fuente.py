"""
Sincronizacion de estado/dia_emision de una serie contra su fuente.

Modulo neutral a proposito: no importa views ni tasks, solo scrapers y django.
Asi los endpoints de lectura y las tareas en background reutilizan exactamente
la misma logica y el mismo cooldown, sin riesgo de import circular.
"""

from datetime import timedelta

from django.utils import timezone

from .scrapers import get_scraper

# Cooldown: no volver a verificar contra la fuente antes de este plazo.
REFRESH_ESTADO_HORAS = 24

# Pausa entre scrapes reales contra la fuente.
SCRAPE_DELAY_SEGUNDOS = 0.3


def verificacion_vencida(serie, ahora=None) -> bool:
    """True si la serie puede volver a verificarse contra la fuente.

    Separado de `actualizar_estado_serie` porque el llamador necesita saber si
    hubo un intento de scrape aunque este haya fallado: es la condicion que
    governa el pacing, y con el cooldown de 24h el "hubo scrape" ya no se puede
    leer del valor de retorno (ver `actualizar_estado_serie`).
    """
    ahora = ahora or timezone.now()
    return (
        not serie.ultima_verificacion
        or serie.ultima_verificacion <= ahora - timedelta(hours=REFRESH_ESTADO_HORAS)
    )


def actualizar_estado_serie(serie, info=None):
    """Actualiza estado y dia_emision de una serie desde la fuente.

    Re-verifica contra la fuente solo si ultima_verificacion esta vencida
    (REFRESH_ESTADO_HORAS), para no martillar a jkanime y evitar bloqueos.
    Si `info` ya fue scrapeado por el caller, se aplica sin re-scrapear.

    Returns:
        bool: True solo si hubo un scrape EXITOSO contra la fuente y se
        escribieron datos. False tanto por cooldown como por scrape fallido:
        un fallo no cuenta como verificacion, y el llamador no debe contarlo
        ni dormir por el (`verificacion_vencida` dice si hubo intento).
    """
    ahora = timezone.now()

    if info is None and not verificacion_vencida(serie, ahora):
        return False

    if info is None:
        try:
            s = get_scraper(serie.fuente)
            info = s.get_series_info(serie.url)
        except Exception:
            info = None

    # Un fallo NO puede comer el cooldown. Sellar ultima_verificacion cuando
    # info es None convierte un 503 o un timeout de un segundo en 24h de estado
    # congelado en local: la fuente vuelve al minuto pero la serie sigue
    # bloqueada hasta mañana. Y `info is None` no distingue "esta serie no
    # tiene info" de "no pude leerla", y las dos cosas piden reintentar.
    if not info:
        return False

    changes = ['ultima_verificacion']
    serie.ultima_verificacion = ahora

    if info.get('estado') and info['estado'] != serie.estado:
        serie.estado = info['estado']
        changes.append('estado')

    dia_scraped = info.get('dia_emision')
    if dia_scraped and dia_scraped != serie.dia_emision:
        serie.dia_emision = dia_scraped
        changes.append('dia_emision')

    serie.save(update_fields=changes)
    return True
