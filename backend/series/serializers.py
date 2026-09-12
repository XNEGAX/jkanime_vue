from django.db.models import Max
from rest_framework import serializers
from .models import Serie, Capitulo


class CapituloSerializer(serializers.ModelSerializer):
    archivo_existe = serializers.BooleanField(read_only=True)
    nombre_archivo = serializers.CharField(read_only=True)
    ruta_smb = serializers.SerializerMethodField()

    class Meta:
        model = Capitulo
        fields = ['id', 'numero', 'nombre_archivo', 'archivo_existe', 'url_fuente', 'fecha_publicacion', 'ruta_smb', 'ultimo_segundo']

    def get_ruta_smb(self, obj):
        if not obj.ruta_archivo:
            return None
        return f"{obj.serie.slug}/{obj.nombre_archivo}"


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
        return obj.capitulos.filter(ruta_archivo__isnull=False).count()

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
    ruta_smb = serializers.SerializerMethodField()
    anterior_id = serializers.SerializerMethodField()
    siguiente_id = serializers.SerializerMethodField()

    class Meta:
        model = Capitulo
        fields = [
            'id', 'numero', 'nombre_archivo', 'archivo_existe', 'fecha_publicacion',
            'url_fuente', 'serie_id', 'serie_nombre', 'ruta_smb',
            'anterior_id', 'siguiente_id', 'ultimo_segundo',
        ]

    def get_ruta_smb(self, obj):
        if not obj.ruta_archivo:
            return None
        return f"{obj.serie.slug}/{obj.nombre_archivo}"

    def get_anterior_id(self, obj):
        cap = Capitulo.objects.filter(serie=obj.serie, numero__lt=obj.numero).order_by('-numero').first()
        return cap.id if cap else None

    def get_siguiente_id(self, obj):
        cap = Capitulo.objects.filter(serie=obj.serie, numero__gt=obj.numero).order_by('numero').first()
        return cap.id if cap else None


class SerieAdminSerializer(serializers.ModelSerializer):
    portada_url = serializers.SerializerMethodField()
    capitulos_count = serializers.SerializerMethodField()
    descargados_count = serializers.SerializerMethodField()
    latest_fecha = serializers.SerializerMethodField()

    class Meta:
        model = Serie
        fields = [
            'id', 'nombre', 'anio', 'portada', 'portada_url', 'url', 'slug',
            'favorito', 'estado', 'dia_emision', 'fuente', 'created_at',
            'capitulos_count', 'descargados_count', 'latest_fecha',
        ]
        read_only_fields = [
            'id', 'portada_url', 'slug', 'created_at',
            'capitulos_count', 'descargados_count', 'latest_fecha',
        ]

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
        return obj.capitulos.filter(ruta_archivo__isnull=False).count()

    def get_latest_fecha(self, obj):
        latest = obj.capitulos.filter(
            fecha_publicacion__isnull=False
        ).order_by('-fecha_publicacion').values_list('fecha_publicacion', flat=True).first()
        return latest.isoformat() if latest else None


class CapituloAdminSerializer(serializers.ModelSerializer):
    serie = serializers.PrimaryKeyRelatedField(queryset=Serie.objects.all())
    serie_nombre = serializers.CharField(source='serie.nombre', read_only=True)
    archivo_existe = serializers.BooleanField(read_only=True)
    nombre_archivo = serializers.CharField(read_only=True)

    class Meta:
        model = Capitulo
        fields = [
            'id', 'serie', 'serie_nombre', 'numero', 'fecha_publicacion',
            'url_fuente', 'ruta_archivo', 'ultimo_segundo',
            'archivo_existe', 'nombre_archivo',
        ]
        read_only_fields = ['id', 'serie_nombre', 'archivo_existe', 'nombre_archivo']
