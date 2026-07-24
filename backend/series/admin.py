from django.contrib import admin
from .models import Serie, Capitulo

@admin.register(Serie)
class SerieAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'anio', 'slug', 'created_at']
    search_fields = ['nombre', 'slug']
    list_filter = ['anio']

@admin.register(Capitulo)
class CapituloAdmin(admin.ModelAdmin):
    list_display = ['serie', 'numero', 'archivo_existe']
    list_filter = ['serie']
