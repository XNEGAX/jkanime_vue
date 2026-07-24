from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from series.models import Capitulo


class Command(BaseCommand):
    help = 'Renombra archivos descargados al formato Episodio-X.mp4 y actualiza ruta_archivo'

    def handle(self, *args, **options):
        download_dir = Path(settings.DOWNLOAD_DIR)
        cap_con_archivo = Capitulo.objects.filter(ruta_archivo__isnull=False).select_related('serie')

        renovados = 0
        saltados = 0
        errores = 0

        for cap in cap_con_archivo:
            old_path = Path(cap.ruta_archivo)
            if not old_path.exists():
                self.stderr.write(f"[saltado] archivo no existe: {old_path}")
                saltados += 1
                continue

            new_path = download_dir / cap.serie.slug / cap.nombre_archivo
            if old_path == new_path:
                saltados += 1
                continue

            if new_path.exists():
                self.stdout.write(f"[saltado] ya existe: {new_path}")
                saltados += 1
                continue

            new_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                old_path.rename(new_path)
            except OSError as e:
                self.stderr.write(f"[error] renombrando {old_path} -> {new_path}: {e}")
                errores += 1
                continue

            cap.ruta_archivo = str(new_path)
            cap.save(update_fields=['ruta_archivo'])
            renovados += 1
            self.stdout.write(f"[ok] {old_path.name} -> {new_path.name}")

        self.stdout.write(self.style.SUCCESS(
            f"Listo: {renovados} renovados, {saltados} saltados, {errores} errores"
        ))
