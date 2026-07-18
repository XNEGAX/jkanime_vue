from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve as static_serve
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('series.urls')),
]

# Serve media files in both debug and production
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Serve Vue dist assets (CSS, JS, images)
dist_dir = str(settings.BASE_DIR.parent / 'frontend' / 'dist')
urlpatterns += [
    re_path(r'^assets/(?P<path>.*)$', static_serve, {'document_root': f'{dist_dir}/assets'}),
]

# SPA fallback — serve index.html for all non-API, non-asset routes
urlpatterns += [
    re_path(r'^(?!api/|assets/).*$', TemplateView.as_view(template_name='index.html'), name='spa'),
]
