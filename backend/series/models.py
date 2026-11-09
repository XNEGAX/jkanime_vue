import os
import re

from django.db import models
from django.conf import settings


class Serie(models.Model):
    ESTADO_CHOICES = [
        ('en_emision', 'En emision'),
        ('concluido', 'Concluido'),
        ('desconocido', 'Desconocido'),
    ]

    DIA_CHOICES = [
        ('lunes', 'Lunes'),
        ('martes', 'Martes'),
        ('miercoles', 'Miércoles'),
        ('jueves', 'Jueves'),
        ('viernes', 'Viernes'),
        ('sabado', 'Sábado'),
        ('domingo', 'Domingo'),
        ('', 'Sin definir'),
    ]

    nombre = models.CharField(max_length=255)
    anio = models.IntegerField("Año", default=2024)
    portada = models.ImageField(upload_to='portadas/', blank=True, null=True)
    url = models.URLField(max_length=500, help_text="URL de la serie en la fuente")
    slug = models.SlugField(max_length=255, blank=True)
    favorito = models.BooleanField(default=False)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='desconocido')
    dia_emision = models.CharField(max_length=15, choices=DIA_CHOICES, default='', blank=True)
    ultima_verificacion = models.DateTimeField(
        null=True, blank=True,
        help_text="Ultimo intento de verificar estado contra la fuente (cooldown para no bloquear jkanime)",
    )
    fuente = models.CharField(max_length=50, default='jkanime', help_text="Fuente: jkanime, latanime")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Serie"
        verbose_name_plural = "Series"
        ordering = ['nombre']
        db_table = 'serie'

    def __str__(self):
        return self.nombre

    def _slug_from_youtube_url(self):
        """Slug `youtube-<playlist|video id>` para series de YouTube."""
        playlist_match = re.search(r'[?&]list=([a-zA-Z0-9_-]+)', self.url or '')
        if playlist_match:
            return f"youtube-{playlist_match.group(1)}"
        video_match = re.search(
            r'(?:v=|youtu\.be/|/embed/|/shorts/|/live/)([a-zA-Z0-9_-]{11})',
            self.url or '',
        )
        return f"youtube-{video_match.group(1)}" if video_match else ''

    def save(self, *args, **kwargs):
        if not self.slug and self.url:
            if self.fuente == 'youtube':
                self.slug = self._slug_from_youtube_url()
            if not self.slug:
                parts = self.url.rstrip('/').split('/')
                if len(parts) >= 4:
                    self.slug = parts[3]
        super().save(*args, **kwargs)


class Capitulo(models.Model):
    serie = models.ForeignKey(Serie, on_delete=models.CASCADE, related_name='capitulos')
    numero = models.IntegerField("Número de capítulo")
    fecha_publicacion = models.DateTimeField("Fecha de publicación", null=True, blank=True)
    ruta_archivo = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Ruta donde se guardo el archivo fisico del capitulo",
    )
    url_fuente = models.URLField(max_length=500, help_text="URL del capítulo en la fuente")
    ultimo_segundo = models.IntegerField("Último segundo visto", default=0, blank=True)

    class Meta:
        verbose_name = "Capítulo"
        verbose_name_plural = "Capítulos"
        ordering = ['numero']
        unique_together = ['serie', 'numero']
        db_table = 'capitulo'

    def __str__(self):
        return f"{self.serie.nombre} - Ep {self.numero}"

    @property
    def ruta_archivo_real(self):
        """
        Ruta real del archivo en disco, o None si no existe.

        No siempre coincide con `ruta_archivo`: esa columna puede quedar vacia
        (NULL) aunque el archivo siga en disco, por ejemplo cuando un borrado
        fallo porque el archivo estaba bloqueado (en Windows no se puede borrar
        con un handle abierto). En ese caso se resuelve la ruta canonica.

        Devuelve la ruta (str), no un booleano, para que quien valide, borre o
        reproduzca el archivo use SIEMPRE una ruta existente y nunca `None`.
        """
        if self.ruta_archivo and os.path.isfile(self.ruta_archivo):
            return self.ruta_archivo

        slug_fuente = self._slug_para_ruta_archivo()
        if not slug_fuente:
            return None
        slug, fuente = slug_fuente
        try:
            from .paths import serie_download_dir
            expected = serie_download_dir(slug, fuente) / self.nombre_archivo
        except Exception:
            return None
        if expected.is_file():
            return str(expected)
        return None

    def _slug_para_ruta_archivo(self):
        """Devuelve `(slug, fuente)` de la serie, o None si no se puede resolver.

        La carpeta de descargas es `"<fuente>-<slug>"` (ver `series.paths`): por
        eso la fuente viaja junto al slug. Sin ella, todo capitulo migrado
        reportaria `archivo_existe=False`. Se tolera que la relacion no este
        precargada, para no forzar un query extra en el camino normal.
        """
        try:
            return self.serie.slug, self.serie.fuente
        except Exception:
            pass
        try:
            from django.apps import apps
            SerieModel = apps.get_model('series', 'Serie')
            serie = SerieModel.objects.only('slug', 'fuente').get(id=self.serie_id)
            return serie.slug, serie.fuente
        except Exception:
            return None

    @property
    def archivo_existe(self):
        return self.ruta_archivo_real is not None

    @property
    def nombre_archivo(self):
        return f"Episodio-{self.numero}.mp4"


class ServerStat(models.Model):
    """Learned reliability of a download server for a given source.

    One row per (fuente, servidor) pair. The download path increments `exitos`
    or `fallos` per real attempt, and `server_stats.rank()` uses the resulting
    smoothed success rate to order the scraper candidates for that source.

    `fuente` reuses the same vocabulary as `Serie.fuente` ('jkanime',
    'latanime', ...) so a pair is keyed by exactly the source identifier the rest
    of the app already stores.
    """

    fuente = models.CharField(
        max_length=50,
        verbose_name="Fuente",
        help_text="Fuente de la serie: jkanime, latanime",
    )
    servidor = models.CharField(max_length=100, verbose_name="Servidor")
    exitos = models.PositiveIntegerField(default=0, verbose_name="Éxitos")
    fallos = models.PositiveIntegerField(default=0, verbose_name="Fallos")
    ultima_vez = models.DateTimeField(auto_now=True, verbose_name="Última vez")

    class Meta:
        verbose_name = "Estadística de servidor"
        verbose_name_plural = "Estadísticas de servidores"
        db_table = 'server_stat'
        unique_together = ['fuente', 'servidor']
        ordering = ['fuente', 'servidor']

    def __str__(self):
        return f"{self.fuente}/{self.servidor} (+{self.exitos}/-{self.fallos})"
