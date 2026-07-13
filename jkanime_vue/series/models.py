import os
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
    url = models.URLField(max_length=500, help_text="URL de la serie en JKanime")
    slug = models.SlugField(max_length=255, blank=True)
    favorito = models.BooleanField(default=False)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='desconocido')
    dia_emision = models.CharField(max_length=15, choices=DIA_CHOICES, default='', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Serie"
        verbose_name_plural = "Series"
        ordering = ['nombre']
        db_table = 'serie'

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if not self.slug and self.url:
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
    url_jkanime = models.URLField(max_length=500, help_text="URL del capítulo en JKanime")

    class Meta:
        verbose_name = "Capítulo"
        verbose_name_plural = "Capítulos"
        ordering = ['numero']
        unique_together = ['serie', 'numero']
        db_table = 'capitulo'

    def __str__(self):
        return f"{self.serie.nombre} - Ep {self.numero}"

    @property
    def archivo_existe(self):
        if not self.ruta_archivo:
            return False
        return os.path.isfile(self.ruta_archivo)

    @property
    def nombre_archivo(self):
        return f"Episodio-{self.numero}.mp4"
