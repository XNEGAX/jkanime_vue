from django.urls import path
from . import views

urlpatterns = [
    path('series/', views.api_series, name='api_series'),
    path('series/favoritos/', views.api_series_favoritos, name='api_series_favoritos'),
    path('series/<int:serie_id>/favorito/', views.api_toggle_favorito, name='api_toggle_favorito'),
    path('series/<int:serie_id>/', views.api_serie_detail, name='api_serie_detail'),
    path('series/<int:serie_id>/capitulos/', views.api_capitulos, name='api_capitulos'),
    path('series/verificar/', views.api_verificar_series, name='api_verificar_series'),
    path('series/agregar-url/', views.api_agregar_serie_url, name='api_agregar_serie_url'),
    path('series/<int:serie_id>/descargar-todos/', views.api_descargar_todos, name='api_descargar_todos'),
    path('capitulos/<int:capitulo_id>/', views.api_capitulo_detail, name='api_capitulo_detail'),
    path('capitulos/<int:capitulo_id>/descargar/', views.api_descargar_capitulo, name='api_descargar_capitulo'),
    path('tareas/activas/', views.api_tareas_activas, name='api_tareas_activas'),
    path('tareas/<str:task_id>/cancelar/', views.api_cancelar_tarea, name='api_cancelar_tarea'),
    path('tareas/<str:task_id>/', views.api_estado_tarea, name='api_estado_tarea'),
    path('video/<int:capitulo_id>/', views.api_servir_video, name='api_servir_video'),
]
