"""
Migra las carpetas de descarga del esquema viejo `<slug>` al nuevo `<fuente>-<slug>`.

Motivo: el slug no es unico (la misma serie puede existir una vez por fuente, ver
series 412 y 445, ambas `tank-chair`). Con la carpeta derivada solo del slug, dos
series distintas compartian `Episodio-N.mp4` y el resultado era "Ya existe" para
la que llegaba segunda, o sobreescritura silenciosa del archivo ajeno.

Que hace:
  - Carpeta vieja que mapea a UNA sola serie: la renombra a `<fuente>-<slug>` y
    reapunta los `Capitulo.ruta_archivo` que apuntaban a la carpeta vieja.
  - Carpeta vieja compartida por series con DISTINTA fuente: copia la carpeta a
    cada `<fuente>-<slug>` para que ninguna serie pierda su archivo, deja la
    carpeta original intacta y la reporta como huerfana removible.
  - Carpeta vieja compartida por series con la MISMA fuente y slug (filas
    duplicadas): se renombra una sola vez; ambas series comparten el destino.

Garantias:
  - `--dry-run` imprime el plan y NO modifica nada.
  - Idempotente: correrlo dos veces no rompe nada.
  - Nunca borra datos del usuario (ni `unlink` ni `rmtree` sobre contenido real).
  - Tolerante a archivos bloqueados en Windows: un `OSError` se registra y se
    cuenta como error sin abortar la corrida completa.
"""

import hashlib
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from series.models import Serie
from series.paths import HASH_LEN, MAX_PATH_SEGURO, NOMBRE_ARCHIVO_RESERVA, serie_dir_name


def _nombre_carpeta_legado(slug: str) -> str:
    """Nombre de carpeta que usaba el esquema viejo (solo slug).

    Replica el truncado+hash anterior para poder reconocer las carpetas que ya
    estan en disco, sin depender de `serie_dir_name` (que ahora exige `fuente`).
    """
    base = str(settings.DOWNLOAD_DIR)
    max_dir = MAX_PATH_SEGURO - len(base) - 2 - NOMBRE_ARCHIVO_RESERVA
    if len(slug) <= max_dir:
        return slug
    digest = hashlib.md5(slug.encode("utf-8")).hexdigest()[:HASH_LEN]
    return f"{slug[:max_dir - HASH_LEN - 1]}-{digest}"


class Command(BaseCommand):
    help = ("Migra las descargas de <slug> a <fuente>-<slug> "
            "(ver series.paths). Usar --dry-run para solo ver el plan.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Imprime el plan sin modificar nada en disco ni en la base',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        base = Path(settings.DOWNLOAD_DIR)

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY-RUN: no se modifica nada."))

        if not base.is_dir():
            self.stdout.write(self.style.WARNING(f"No existe {base}; nada para migrar."))
            return

        # Agrupa las series por el nombre de carpeta del esquema viejo. Dos series
        # con el mismo slug (y distinta fuente) caen en el MISMO grupo: esa es la
        # colision que hay que resolver.
        series_por_legado = {}
        for serie in Serie.objects.exclude(slug='').only('id', 'slug', 'fuente'):
            series_por_legado.setdefault(_nombre_carpeta_legado(serie.slug), []).append(serie)

        renombradas = copiadas = reapuntados = saltadas = errores = 0
        huerfanas = []

        for carpeta in sorted(p for p in base.iterdir() if p.is_dir()):
            candidatas = series_por_legado.get(carpeta.name)
            if not candidatas:
                # Ya esta en el esquema nuevo, o no pertenece a ninguna serie.
                continue

            # Destino canonico por serie, agrupado por nombre de carpeta.
            destinos = {}
            for serie in candidatas:
                destinos.setdefault(serie_dir_name(serie.slug, serie.fuente), []).append(serie)

            if len(destinos) == 1:
                # Un unico destino: renombrar (barato, mismo volumen).
                nombre_destino, grupo = next(iter(destinos.items()))
                destino = base / nombre_destino
                if destino.exists():
                    self.stdout.write(f"[saltado] ya existe el destino: {destino}")
                    saltadas += 1
                    continue
                self.stdout.write(f"[renombrar] {carpeta.name} -> {nombre_destino}")
                if not dry_run:
                    try:
                        carpeta.rename(destino)
                    except OSError as e:
                        self.stderr.write(f"[error] renombrando {carpeta} -> {destino}: {e}")
                        errores += 1
                        continue
                renombradas += 1
                reapuntados += self._reapuntar(grupo, carpeta, destino, aplicar=not dry_run)
                continue

            # Colision real: series de distinta fuente comparten la misma carpeta.
            # Se COPIA a cada destino para que ninguna pierda su archivo y la
            # carpeta original queda como huerfana removible.
            for nombre_destino, grupo in destinos.items():
                if not self._alguna_reclama(carpeta, grupo):
                    continue
                destino = base / nombre_destino
                if destino.exists():
                    self.stdout.write(f"[saltado] ya existe el destino: {destino}")
                    saltadas += 1
                else:
                    self.stdout.write(f"[copiar] {carpeta.name} -> {nombre_destino}")
                    if not dry_run:
                        try:
                            shutil.copytree(carpeta, destino)
                        except OSError as e:
                            self.stderr.write(f"[error] copiando {carpeta} -> {destino}: {e}")
                            errores += 1
                            continue
                    copiadas += 1
                reapuntados += self._reapuntar(grupo, carpeta, destino, aplicar=not dry_run)
            huerfanas.append(str(carpeta))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Listo: {renombradas} carpetas renombradas, {copiadas} copiadas, "
            f"{reapuntados} capitulos reapuntados, {saltadas} saltadas, {errores} errores"
        ))
        if huerfanas:
            self.stdout.write("Carpetas huerfanas (contenido ya copiado, se pueden borrar a mano):")
            for ruta in huerfanas:
                self.stdout.write(f"  - {ruta}")

    # ------------------------------------------------------------------
    # Internas
    # ------------------------------------------------------------------

    def _alguna_reclama(self, carpeta: Path, series) -> bool:
        """True si alguna serie tiene un capitulo que apunta a `carpeta` o un archivo ahi."""
        for serie in series:
            for cap in serie.capitulos.all():
                if cap.ruta_archivo and Path(cap.ruta_archivo).parent == carpeta:
                    return True
                if (carpeta / cap.nombre_archivo).is_file():
                    return True
        return False

    def _reapuntar(self, series, origen: Path, destino: Path, aplicar: bool) -> int:
        """Actualiza `Capitulo.ruta_archivo` de `origen` hacia `destino`.

        Solo toca capitulos cuyo `ruta_archivo` apuntaba a `origen`, o que tienen
        la columna vacia y el archivo ya esta en `destino` (auto-sanado). Nunca
        pisa una ruta valida que apunte a otro lado. Con `aplicar=False` cuenta
        sin guardar (modo dry-run).
        """
        cambiados = 0
        for serie in series:
            for cap in serie.capitulos.all():
                nueva = destino / cap.nombre_archivo
                actual = cap.ruta_archivo
                apuntaba_al_origen = bool(actual) and Path(actual).parent == origen
                # En dry-run el rename todavia no ocurrio: mirar tambien el origen.
                archivo_disponible = nueva.is_file() or (origen / cap.nombre_archivo).is_file()
                if not apuntaba_al_origen and not (not actual and archivo_disponible):
                    continue
                texto = str(nueva)
                if actual == texto:
                    continue
                cambiados += 1
                if aplicar:
                    cap.ruta_archivo = texto
                    cap.save(update_fields=['ruta_archivo'])
        return cambiados
