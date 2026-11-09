"""
Rutas de descarga acotadas al limite de path de Windows.

La ruta de un capitulo es `DOWNLOAD_DIR/<fuente>-<slug>/Episodio-N.mp4`. El slug
NO es unico por si solo: la misma serie puede existir una vez por fuente (ver
series 412 y 445, ambas `tank-chair` pero de jkanime y latanime). Una carpeta
derivada solo del slug hacia que las dos compartieran `Episodio-N.mp4`: la que
descargaba primero dejaba a la otra con "Ya existe" para siempre, y volver a
descargar una sobreescribia en silencio el archivo de la otra. Prefijar con
`fuente` vuelve la carpeta funcion pura de `(fuente, slug)` y elimina la
colision.

jkanime tiene slugs de hasta 220 caracteres (ver serie 450): la ruta completa
pasa de los 260 de `MAX_PATH` y `Path.mkdir()` falla con `WinError 3` ("no se
puede encontrar la ruta"), que NO dice "ruta demasiado larga". El resultado era
que la descarga moria antes de empezar y el usuario veia "no inicia".

Este modulo centraliza el nombre de carpeta para que todos los lugares que arman
la ruta (tasks, views, task_runner, rename_descargas, models, serializers) no
puedan divergir.
"""

import hashlib
from pathlib import Path

from django.conf import settings

# MAX_PATH de Windows es 260. Se deja margen para el separador, el nombre de
# archivo mas largo posible y posibles sufijos que agregue el SO.
MAX_PATH_SEGURO = 240
NOMBRE_ARCHIVO_RESERVA = len("Episodio-9999.mp4")
HASH_LEN = 8


def serie_dir_name(slug: str, fuente: str) -> str:
    """Nombre de carpeta de descargas para `(fuente, slug)`, acotado a MAX_PATH_SEGURO.

    El slug por si solo no alcanza: dos series con el mismo slug pero distinta
    fuente compartirian carpeta. Por eso la carpeta es `"<fuente>-<slug>"`.

    Los nombres que ya entran en el limite se devuelven tal cual: no renombra las
    descargas existentes. Los que no entran truncan la parte del slug y agregan
    un hash corto del nombre COMPLETO (`fuente` incluida), para que dos series
    con el mismo prefijo no terminen compartiendo carpeta.

    `fuente` es obligatorio y no tiene valor por defecto A PROPOSITO: un call
    site que se olvide de pasarlo debe fallar con `TypeError` en vez de caer en
    silencio a la carpeta vieja (derivada solo del slug) y volver a colisionar.
    """
    nombre = f"{fuente}-{slug}"
    base = str(settings.DOWNLOAD_DIR)
    max_dir = MAX_PATH_SEGURO - len(base) - 2 - NOMBRE_ARCHIVO_RESERVA
    if len(nombre) <= max_dir:
        return nombre
    # El digest se calcula sobre el nombre completo para que no lo puedan eludir
    # dos series con el mismo prefijo de slug.
    digest = hashlib.md5(nombre.encode("utf-8")).hexdigest()[:HASH_LEN]
    # El prefijo `<fuente>-` se conserva entero: el presupuesto de truncado es
    # para el slug, descontando el prefijo y el propio hash.
    prefijo = f"{fuente}-"
    cupo_slug = max_dir - len(prefijo) - HASH_LEN - 1
    return f"{prefijo}{slug[:cupo_slug]}-{digest}"


def serie_download_dir(slug: str, fuente: str) -> Path:
    """Directorio de descargas de una serie. El caller lo crea si hace falta."""
    return Path(settings.DOWNLOAD_DIR) / serie_dir_name(slug, fuente)
