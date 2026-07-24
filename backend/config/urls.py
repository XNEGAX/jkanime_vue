from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.static import serve as static_serve


@never_cache
def spa_fallback(request):
    """Sirve index.html con Cache-Control: no-cache para que el navegador
    siempre pida el HTML mas reciente (y con eso los assets hasheados)."""
    return render(request, 'index.html')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('series.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Serve Vue dist assets (CSS, JS, images) — estos SÍ se cachean porque tienen hash
dist_dir = str(settings.BASE_DIR.parent / 'frontend' / 'dist')
urlpatterns += [
    re_path(r'^assets/(?P<path>.*)$', static_serve, {'document_root': f'{dist_dir}/assets'}),
]

# SPA fallback — serve index.html with no-cache headers
urlpatterns += [
    re_path(r'^(?!api/|assets/).*$', spa_fallback, name='spa'),
]
