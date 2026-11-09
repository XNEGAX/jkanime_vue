from django.contrib import admin
from .models import Serie, Capitulo, ServerStat

@admin.register(Serie)
class SerieAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'anio', 'slug', 'created_at']
    search_fields = ['nombre', 'slug']

@admin.register(Capitulo)
class CapituloAdmin(admin.ModelAdmin):
    list_display = ['serie', 'numero', 'archivo_existe']
    list_filter = ['serie']


@admin.register(ServerStat)
class ServerStatAdmin(admin.ModelAdmin):
    """Inspection-only view of the learned server statistics.

    The counters are maintained by the download path (`server_stats.record`),
    so they are read-only here to keep hand-edits from skewing the ranking.
    """

    list_display = ['fuente', 'servidor', 'exitos', 'fallos', 'ultima_vez']
    list_filter = ['fuente']
    search_fields = ['servidor']
    readonly_fields = ['exitos', 'fallos', 'ultima_vez']
    ordering = ['fuente', 'servidor']
