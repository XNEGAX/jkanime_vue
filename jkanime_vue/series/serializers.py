from django.db.models import Max
from rest_framework import serializers
from .models import Serie, Capitulo


class CapituloSerializer(serializers.ModelSerializer):
    archivo_existe = serializers.BooleanField(read_only=True)
    nombre_archivo = serializers.CharField(read_only=True)

    class Meta:
        model = Capitulo
        fields = ['id', 'numero', 'nombre_archivo', 'archivo_existe', 'url_jkanime', 'fecha_publicacion']


class SerieListSerializer(serializers.ModelSerializer):
    portada_url = serializers.SerializerMethodField()
    capitulos_count = serializers.SerializerMethodField()
    descargados_count = serializers.SerializerMethodField()
    latest_fecha = serializers.SerializerMethodField()

    class Meta:
        model = Serie
        fields = ['id', 'nombre', 'anio', 'portada_url', 'slug', 'favorito', 'estado', 'dia_emision', 'latest_fecha', 'capitulos_count', 'descargados_count']

    def get_portada_url(self, obj):
        if obj.portada:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.portada.url)
            return obj.portada.url
        return None

    def get_capitulos_count(self, obj):
        return obj.capitulos.count()

    def get_descargados_count(self, obj):
        return sum(1 for c in obj.capitulos.all() if c.archivo_existe)

    def get_latest_fecha(self, obj):
        latest = obj.capitulos.filter(
            fecha_publicacion__isnull=False
        ).order_by('-fecha_publicacion').values_list('fecha_publicacion', flat=True).first()
        return latest.isoformat() if latest else None


class SerieDetailSerializer(serializers.ModelSerializer):
    portada_url = serializers.SerializerMethodField()
    capitulos = CapituloSerializer(many=True, read_only=True)

    class Meta:
        model = Serie
        fields = ['id', 'nombre', 'anio', 'portada_url', 'slug', 'favorito', 'estado', 'dia_emision', 'capitulos']

    def get_portada_url(self, obj):
        if obj.portada:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.portada.url)
            return obj.portada.url
        return None


class CapituloDetailSerializer(serializers.ModelSerializer):
    serie_nombre = serializers.CharField(source='serie.nombre', read_only=True)
    serie_id = serializers.IntegerField(source='serie.id', read_only=True)
    archivo_existe = serializers.BooleanField(read_only=True)
    nombre_archivo = serializers.CharField(read_only=True)
    anterior_id = serializers.SerializerMethodField()
    siguiente_id = serializers.SerializerMethodField()

    class Meta:
        model = Capitulo
        fields = [
            'id', 'numero', 'nombre_archivo', 'archivo_existe', 'fecha_publicacion',
            'url_jkanime', 'serie_id', 'serie_nombre',
            'anterior_id', 'siguiente_id',
        ]

    def get_anterior_id(self, obj):
        cap = Capitulo.objects.filter(serie=obj.serie, numero__lt=obj.numero).order_by('-numero').first()
        return cap.id if cap else None

    def get_siguiente_id(self, obj):
        cap = Capitulo.objects.filter(serie=obj.serie, numero__gt=obj.numero).order_by('numero').first()
        return cap.id if cap else None
