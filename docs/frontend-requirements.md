# AnimeWing — Requerimientos extraídos del Frontend

> Ingeniería inversa sobre `frontend/src/` — Julio 2026

---

## 1. Gestión de Configuración del Servidor

| ID | Requerimiento |
|----|---------------|
| CFG-01 | La app debe detectar si se ejecuta en entorno nativo (Capacitor) o navegador web |
| CFG-02 | Al iniciar en Capacitor sin configuración guardada, debe mostrar la pantalla de configuración como pantalla inicial obligatoria |
| CFG-03 | El usuario debe poder configurar manualmente el host y puerto del servidor Django |
| CFG-04 | El campo puerto debe validarse como número entre 1 y 65535 |
| CFG-05 | Al guardar la configuración, debe probar la conexión contra `GET /api/series/` |
| CFG-06 | Si la prueba de conexión falla, debe mostrar el error al usuario y no cerrar el modal |
| CFG-07 | La configuración debe persistirse en Capacitor Preferences con fallback a localStorage |
| CFG-08 | El usuario debe poder borrar la configuración guardada |
| CFG-09 | En Capacitor, guardar la configuración debe recargar la app para que todos los componentes usen la nueva URL base |
| CFG-10 | Cada request API debe usar dinámicamente la URL base configurada (host:puerto) |

---

## 2. Exploración y Búsqueda de Series

| ID | Requerimiento |
|----|---------------|
| SER-01 | La pantalla principal debe listar todas las series disponibles agrupadas por día de emisión |
| SER-02 | Los grupos de días deben rotarse para que el día actual aparezca primero |
| SER-03 | La navegación entre días debe ser paginada (un día por página) con botones de paginación |
| SER-04 | La página actual debe persistirse en la URL como query param `pagina` |
| SER-05 | La paginación debe mostrar hasta 7 botones de día con "..." para rangos extensos |
| SER-06 | Las series concluidas no deben aparecer en la lista principal |
| SER-07 | Las series sin actividad en los últimos 14 días no deben aparecer en la lista principal |
| SER-08 | El usuario debe poder buscar series por nombre desde la barra de navegación con debounce de 300ms |
| SER-09 | El término de búsqueda debe persistirse en la URL como query param `search` |
| SER-10 | La lista de series debe mostrar portada (80×60), nombre, estado y conteo de capítulos |
| SER-11 | Las series con capítulos descargados deben mostrar "descargados/total" con badge verde |
| SER-12 | El usuario debe poder eliminar una serie con confirmación, borrando todos sus capítulos y archivos del disco |
| SER-13 | Al eliminar una serie, debe actualizar el store de favoritos local |

---

## 3. Favoritos

| ID | Requerimiento |
|----|---------------|
| FAV-01 | El usuario debe poder marcar/desmarcar cualquier serie como favorito desde cualquier vista donde aparezca |
| FAV-02 | El toggle de favorito debe llamar al endpoint `POST /api/series/{id}/favorito/` |
| FAV-03 | El estado de favoritos debe mantenerse en un Set en memoria (Pinia) |
| FAV-04 | El Set de favoritos debe poblarse automáticamente al cargar cualquier lista de series que incluya el campo `favorito` |
| FAV-05 | La vista de Favoritos debe tener 3 tabs: Últimos episodios, En emisión, Concluidos |
| FAV-06 | La tab activa debe persistirse en sessionStorage entre navegaciones |
| FAV-07 | El scroll vertical debe restaurarse al volver a la vista de Favoritos |
| FAV-08 | La tab "En emisión" debe listar favoritos agrupados por día de emisión, ordenados desde hoy (día actual primero, en orden descendente) |
| FAV-09 | La tab "En emisión" debe tener filtro de búsqueda por nombre |
| FAV-10 | La tab "Concluidos" debe listar favoritos ordenados alfabéticamente, agrupados por primera letra |
| FAV-11 | La tab "Concluidos" debe tener filtro de búsqueda por nombre |
| FAV-12 | Cada tab debe cargar sus datos una sola vez (lazy load con caché por tab) |
| FAV-13 | El usuario debe poder quitar un favorito directamente desde las cards de las tabs "En emisión" y "Concluidos" |
| FAV-14 | Al quitar un favorito, la serie debe desaparecer de la lista local sin recargar |
| FAV-15 | Las tabs "En emisión" y "Concluidos" deben cargarse con llamadas secuenciales al backend (día a día / grupo de letras), acumulando los resultados en un caché por día/grupo y renderizando todos los grupos apilados |
| FAV-16 | No debe haber chips de filtro por día ni por letra; cada tab muestra todos los grupos apilados y la búsqueda filtra sobre la lista completa |

---

## 4. Capítulos por Serie

| ID | Requerimiento |
|----|---------------|
| CAP-01 | Al navegar a `/serie/:id` debe cargar el detalle de la serie y su lista de capítulos |
| CAP-02 | La vista debe mostrar metadata: total de episodios en la fuente, registrados en BD y nuevos encontrados |
| CAP-03 | Los capítulos deben mostrarse en tabla ordenados por número descendente |
| CAP-04 | Cada capítulo debe mostrar: número, nombre de archivo, fecha de publicación, y botón de acción |
| CAP-05 | El botón de acción debe cambiar según el estado: "Reproducir" (descargado), "Reparar" (corrupto), "Descargando X%" (en progreso), "Iniciando..." (en cola) |
| CAP-06 | Si el capítulo no tiene portada, debe intentar descargarla automáticamente desde la fuente |
| CAP-07 | El usuario debe poder marcar/desmarcar la serie como favorito desde el encabezado |

---

## 5. Descarga de Capítulos

| ID | Requerimiento |
|----|---------------|
| DWL-01 | El usuario debe poder iniciar la descarga de un capítulo individual |
| DWL-02 | El usuario debe poder descargar todos los capítulos faltantes de una serie con un solo botón |
| DWL-03 | Al iniciar una descarga, el frontend debe recibir un `task_id` y comenzar a pollear el estado |
| DWL-04 | El polling debe consultar `GET /api/tareas/{task_id}/` cada 1500ms |
| DWL-05 | Al completarse una descarga, el capítulo debe marcarse como disponible localmente |
| DWL-06 | Si se descarga exitosamente y había un callback de reproducción, debe reproducirse automáticamente |
| DWL-07 | Las descargas activas deben persistir en memoria del servidor y restaurarse al recargar la app |
| DWL-08 | Al restaurar descargas activas, debe abrir el drawer de descargas automáticamente |
| DWL-09 | El usuario debe poder cancelar una descarga en curso |
| DWL-10 | Las descargas completadas o fallidas deben desaparecer de la lista tras 4 segundos |
| DWL-11 | El botón "Descargar todos" debe deshabilitarse si todos los capítulos ya están descargados |
| DWL-12 | Si se detecta un archivo corrupto al iniciar descarga, debe eliminarse y re-descargarse |

---

## 6. Drawer de Descargas

| ID | Requerimiento |
|----|---------------|
| DRW-01 | Debe haber un drawer deslizable desde la derecha que muestre el estado de todas las descargas |
| DRW-02 | El drawer debe ordenar: completados primero, luego en progreso, luego en cola |
| DRW-03 | Debe mostrarse un badge en la barra de navegación con la cantidad de descargas activas, con animación pulsante |
| DRW-04 | El badge debe ser clickeable para abrir/cerrar el drawer |
| DRW-05 | Cada item de descarga debe mostrar: nombre de la serie, número de episodio, fase actual, barra de progreso, bytes descargados/total, porcentaje |
| DRW-06 | Si hay un servidor activo, debe mostrarse su nombre |
| DRW-07 | Las descargas activas deben tener botón para cancelar |
| DRW-08 | Las descargas completadas deben mostrar borde verde |
| DRW-09 | Las descargas fallidas deben mostrar el mensaje de error y opacidad reducida |

---

## 7. Últimos Episodios (Trending)

| ID | Requerimiento |
|----|---------------|
| TRD-01 | La tab "Últimos episodios" debe cargar episodios recientes desde la fuente |
| TRD-02 | Los episodios deben agruparse por categoría (Animes, Donghuas, Ovas) |
| TRD-03 | Cada episodio debe mostrarse como TrendingCard con portada, nombre y número de episodio |
| TRD-04 | Las cards deben organizarse en grilla responsiva CSS (auto-fill, min-width configurable) |
| TRD-05 | Al hacer clic en un episodio: si existe en BD y el archivo es válido, abrir reproductor; si no, ir a la serie o descargar |
| TRD-06 | Si un episodio se está descargando, la card debe mostrar overlay de progreso |
| TRD-07 | Las cards deben ser lazy-loaded en las imágenes |
| TRD-08 | Las cards deben mostrar efecto hover (elevación) |

---

## 8. Verificación de Series

| ID | Requerimiento |
|----|---------------|
| VRF-01 | Al cargar la lista de series, debe iniciarse automáticamente una verificación contra la fuente (jkanime.net) |
| VRF-02 | La verificación debe buscar series nuevas, actualizar estado y día de emisión, y detectar capítulos nuevos |
| VRF-03 | El progreso de la verificación debe mostrarse con spinner y detalle del estado actual |
| VRF-04 | Al completar la verificación, si se encontraron series/capítulos nuevos, debe recargar la lista automáticamente |
| VRF-05 | Si ya hay una verificación en curso al cargar la página, debe conectarse a ella y mostrar su progreso |
| VRF-06 | El estado de la verificación debe pollearse cada 2000ms |

---

## 9. Agregar Serie por URL

| ID | Requerimiento |
|----|---------------|
| URL-01 | El usuario debe poder agregar una serie pegando su URL desde jkanime.net o latanime.org |
| URL-02 | Al agregar la URL, debe mostrar modal con campo de entrada validado |
| URL-03 | Si la serie se agrega exitosamente, debe redirigir a la vista de capítulos de esa serie |
| URL-04 | Si hay error, debe mostrar el mensaje en el modal |

---

## 10. Reproducción de Video

| ID | Requerimiento |
|----|---------------|
| VID-01 | El reproductor debe ocupar toda la pantalla (overlay fijo) |
| VID-02 | Debe mostrar nombre de la serie y número de episodio en el encabezado |
| VID-03 | Debe permitir navegar al episodio anterior/siguiente dentro de la misma serie |
| VID-04 | Si el usuario tiene progreso guardado (>30s), debe preguntar si desea reanudar desde donde lo dejó |
| VID-05 | El progreso de reproducción debe guardarse automáticamente cada 10 segundos vía API |
| VID-06 | Al cerrar el reproductor o recargar la página, debe guardar el progreso via sendBeacon |
| VID-07 | Debe tener botón "Saltar OP" que avance 90 segundos |
| VID-08 | Debe soportar atajos de teclado: Escape (cerrar), Space (play/pause), ←/→ (-10s/+10s), F (fullscreen), S (saltar OP) |
| VID-09 | Si el video falla con error de decodificación (código 3), debe ofrecer botón "Reparar y re-descargar" |
| VID-10 | Si el video falla con error de red (código 2), debe indicar error de conexión |
| VID-11 | Si el video falla por formato no soportado (código 4), debe indicar que no es compatible |

---

## 11. Integridad de Archivos

| ID | Requerimiento |
|----|---------------|
| INT-01 | Antes de reproducir un capítulo descargado, debe verificar la integridad del archivo MP4 |
| INT-02 | Si el archivo está corrupto, debe marcarlo como tal y ofrecer/reparar automáticamente |
| INT-03 | La reparación debe eliminar el archivo corrupto y re-descargarlo |
| INT-04 | El estado de verificación/reparación debe mostrarse en el botón del capítulo |
| INT-05 | La verificación puede hacerse tanto desde la vista de capítulos como desde el reproductor |

---

## 12. Navegación y UX

| ID | Requerimiento |
|----|---------------|
| NAV-01 | La barra de navegación debe ser sticky en la parte superior |
| NAV-02 | El logo "AnimeWing" debe redirigir a la vista principal |
| NAV-03 | El botón de configuración debe abrir el modal de configuración del servidor |
| NAV-04 | La vista de capítulos debe tener botón "Volver" que navegue hacia atrás o a la raíz |
| NAV-05 | La vista de Favoritos debe estar cacheada con `<keep-alive>` |
| NAV-06 | El scroll debe preservarse al navegar entre rutas |
| NAV-07 | La barra de navegación debe incluir búsqueda global de series |
| NAV-08 | Los mensajes de error/éxito deben mostrarse como alertas de colores (verde = éxito, rojo = error) |

---

## 13. Refrescado de Portadas

| ID | Requerimiento |
|----|---------------|
| PRT-01 | Si una serie no tiene portada al cargar su detalle, debe intentar descargarla automáticamente desde la fuente |
| PRT-02 | El refresco de portada debe ser silencioso (no mostrar errores al usuario) |

---

## 14. Capacitor (Android)

| ID | Requerimiento |
|----|---------------|
| CPC-01 | La app debe funcionar como aplicación nativa Android vía Capacitor |
| CPC-02 | Debe detectar automáticamente si es entorno nativo |
| CPC-03 | Sin configuración de servidor guardada, debe mostrar la ConfigScreen como pantalla inicial (no permite saltarla) |
| CPC-04 | La configuración debe persistirse usando @capacitor/preferences |

---

## Notas Técnicas

- **Framework**: Vue 3 (Composition API) + Vite 6
- **Estado**: Pinia con stores modulares (config, downloads, favorites)
- **Ruteo**: Vue Router 4 con `createWebHistory`
- **API**: Axios con interceptor para URL base dinámica
- **Polling**: setInterval 1500ms para descargas, 2000ms para verificación
- **Persistencia local**: sessionStorage para tab activa y scroll, localStorage/Capacitor Preferences para config
- **Favoritos**: `GET /api/series/favoritos/` acepta `estado`, `dia` (filtro exacto por `dia_emision`) y `letras` (OR de `Q(nombre__istartswith=letra)`) para paginar la carga por día/grupo de letras desde el frontend
- **Sin test runner**: no hay tests configurados en el frontend
