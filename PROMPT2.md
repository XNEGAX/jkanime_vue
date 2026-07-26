# Implementación y mejoras para jkanime_vue

## Contexto

Estoy trabajando en el proyecto ubicado en:

`C:\Users\Carlo\Documents\Proyectos\jkanime_vue`

Antes de realizar cualquier cambio debes analizar completamente la arquitectura del proyecto, tanto frontend como backend, para mantener consistencia con el código existente.

## Reglas importantes

- No modificar funcionalidades existentes salvo que se indique explícitamente.
- Mantener el estilo de código actual del proyecto.
- Reutilizar componentes, servicios y composables existentes siempre que sea posible.
- No duplicar lógica.
- Si es necesario crear nuevos componentes, seguir la misma estructura del proyecto.
- Verificar que todos los cambios continúen funcionando tanto en web como en la futura versión Android.

---

# 1. Backend

## Endpoint `/api/ultimos-episodios/`

Una vez obtenida la lista proveniente del scraping, agregar una nueva capa de procesamiento antes de responder.

Para cada elemento:

### Serie

Buscar la serie en la base de datos.

- Si existe:
    - Reemplazar la imagen obtenida mediante scraping por la portada almacenada en la base de datos.
- Si no existe:
    - Crear automáticamente la serie utilizando la información disponible del scraping.

### Episodio

Para cada episodio recibido:

- Verificar si existe en la base de datos.
- Si no existe:
    - Crearlo automáticamente.

La respuesta del endpoint debe seguir manteniendo exactamente el mismo formato utilizado actualmente.

---

# 2. Frontend

## Tab "Últimos episodios"

### Diseño

- Continuar utilizando las tarjetas actuales.
- Agrupar los episodios utilizando el campo `tab` recibido desde el API.

Ejemplo:

```
Hoy
    episodio...
    episodio...

Ayer
    episodio...
```

---

### Acción al hacer click sobre un episodio

Actualmente el click abre la URL de JKAnime en una nueva pestaña.

Eso es incorrecto.

Debe replicarse exactamente la misma lógica utilizada por el botón **Reproducir** existente en la vista de una serie.

Es decir:

- utilizar exactamente el mismo flujo
- reutilizar el mismo código siempre que sea posible
- no abrir JKAnime

---

### Descarga de episodio

Cuando un episodio aún no exista o deba descargarse:

Mostrar sobre la imagen exactamente el mismo indicador utilizado actualmente en la vista de serie.

Debe mostrar:

- loader circular
- porcentaje de descarga (cuando corresponda)
- mensaje de etapa actual

Por ejemplo:

- Buscando...
- Descargando...
- Procesando...
- Finalizado

No crear una implementación distinta.

Debe reutilizar el mismo componente o lógica ya existente.

---

# 3. Tab "En emisión"

Actualmente las series aparecen agrupadas por día.

Se requieren los siguientes cambios.

## Diseño

Las series deben mostrarse utilizando el componente `trending-card`, igual que en otras vistas.

---

## Orden de los grupos

Los grupos siempre deben comenzar desde el día actual y luego retroceder cronológicamente.

Ejemplos:

Si hoy es:

### Lunes

```
Lunes
Domingo
Sábado
Viernes
Jueves
Miércoles
Martes
```

### Sábado

```
Sábado
Viernes
Jueves
Miércoles
Martes
Lunes
Domingo
```

### Miércoles

```
Miércoles
Martes
Lunes
Domingo
Sábado
Viernes
Jueves
```

Es importante que el recorrido siempre sea **hacia atrás**, nunca hacia adelante.

---

# 4. Tab "Concluidos"

Modificar la presentación para utilizar `trending-grid`.

Además:

Agrupar las series por orden alfabético.

Ejemplo:

```
A

Akira
Attack on Titan

B

Bleach

C

Code Geass
```

---

# 5. Navegación

Actualmente:

Inicio

↓

click en una serie

↓

Detalle

↓

Volver

↓

Siempre regresa al inicio.

Eso debe cambiar.

Al regresar desde la vista de una serie, el usuario debe volver exactamente al estado anterior.

Debe conservar:

- tab seleccionado
- posición del scroll
- grupo expandido (si aplica)
- sección visible

Ejemplo:

```
En emisión

↓

Viernes

↓

Click sobre una serie

↓

Detalle

↓

Volver

↓

En emisión

↓

Viernes

↓

Misma posición del scroll
```

Debe sentirse como si nunca hubiera abandonado la pantalla.

---

# 6. Aplicación Android

Analiza el proyecto completo y decide cuál de las siguientes alternativas es la más adecuada.

## Opción 1

Mantener el frontend Vue y generar una aplicación Android utilizando tecnologías compatibles (por ejemplo Capacitor).

## Opción 2

Crear una aplicación Android nativa en Kotlin.

La decisión debe basarse en:

- facilidad de mantenimiento
- reutilización de código
- rendimiento
- experiencia de usuario
- complejidad del proyecto

Justifica la elección antes de comenzar la implementación.

---

## Requisitos de la aplicación Android

La aplicación debe replicar exactamente todas las funcionalidades actuales del frontend web.

No debe existir ninguna funcionalidad diferente.

Todo lo que pueda hacerse desde la versión web debe poder hacerse desde Android.

---

## Configuración inicial

La primera vez que se abra la aplicación debe mostrarse una pantalla de configuración.

Debe solicitar:

- Host
- Puerto

Ejemplo:

```
Host:

192.168.1.15

Puerto:

8000
```

Al guardar:

- almacenar la configuración localmente
- utilizar esos datos para construir la URL base de todas las llamadas al API

En posteriores ejecuciones no debe volver a solicitar estos datos, salvo que el usuario los modifique desde una pantalla de configuración.


---

# 7. Lineamientos de Diseño (UI)

Toda nueva interfaz o modificación visual debe respetar la siguiente guía de diseño inspirada en **Wing Zero Custom**.

El objetivo es mantener una identidad visual consistente en todo el proyecto (web y futura aplicación Android).

No utilizar colores arbitrarios distintos a esta paleta, salvo cuando sea estrictamente necesario para estados del sistema (error, éxito, advertencia, etc.).

## Paleta de Colores

La paleta está basada en la composición cromática de Wing Zero Custom, utilizando una distribución visual equivalente al diseño original.

| Rol | Color | HEX | RGB | Uso | Proporción |
|------|-------|-----|-----|-----|------------|
| Fondo principal | Blanco Pluma / Perlado | `#F7F8FC` | `rgb(247,248,252)` | Fondos generales | **45%** |
| Primario | Azul Cobalto Mecánico | `#00539C` | `rgb(0,83,156)` | Navegación, botones, enlaces | **25%** |
| Texto principal | Gris Grafito Armamento | `#3A3D42` | `rgb(58,61,66)` | Texto, iconografía | **15%** |
| Fondo secundario | Cobre Cálido | `#D18854` | `rgb(209,136,84)` | Cards destacadas, banners, footer | **10%** |
| Acento principal | Amarillo V-Fin | `#F4C430` | `rgb(244,196,48)` | CTA, badges, indicadores | **3%** |
| Acento secundario | Púrpura Nebulosa | `#C8BFE7` | `rgb(200,191,231)` | Hover, sombras y detalles | **2%** |

---

## Variables CSS

Toda la aplicación debe utilizar estas variables CSS como fuente única de colores.

```css
:root {

  /* Colores principales */

  --bg-primary: #F7F8FC;
  --primary: #00539C;
  --text-main: #3A3D42;
  --bg-secondary: #D18854;
  --accent-cta: #F4C430;
  --accent-subtle: #C8BFE7;

  /* Estados derivados */

  --text-muted: #6C757D;
  --border-light: #E2E8F0;

}
```

No utilizar códigos HEX directamente en los componentes cuando exista una variable CSS equivalente.

---

## Guía de uso

### Fondo principal (45%)

Utilizar para:

- background principal
- páginas
- contenedores
- cards claras
- espacios en blanco

Debe transmitir amplitud y limpieza.

---

### Color primario (25%)

Utilizar para:

- Navbar
- Sidebar
- Botones secundarios
- Enlaces
- Tabs activos
- Indicadores activos
- Focus

Debe ser el color representativo de la aplicación.

---

### Texto (15%)

Utilizar para:

- títulos
- párrafos
- iconografía
- etiquetas
- bordes oscuros

Debe garantizar una lectura cómoda.

---

### Fondo secundario (10%)

Utilizar para:

- banners
- secciones especiales
- footer
- tarjetas destacadas
- paneles

Debe aportar contraste sin romper la armonía del diseño.

---

### Amarillo (3%)

Reservar únicamente para elementos de alta importancia.

Ejemplos:

- botón principal
- llamadas a la acción (CTA)
- badges
- indicadores
- elementos destacados

No abusar de este color.

---

### Púrpura (2%)

Utilizar únicamente como detalle visual.

Ejemplos:

- hover de tarjetas
- sombras coloreadas
- separadores
- pequeños degradados
- efectos visuales

Nunca debe convertirse en un color dominante.

---

## Estilo general

La interfaz debe transmitir:

- limpieza
- modernidad
- velocidad
- simplicidad
- sensación tecnológica

Inspirarse en interfaces como:

- Netflix
- Crunchyroll
- Plex
- Steam
- Material Design 3

pero manteniendo identidad propia.

---

## Componentes

Todos los nuevos componentes deben mantener consistencia con los existentes.

Evitar:

- colores aleatorios
- bordes inconsistentes
- radios distintos
- sombras diferentes entre componentes

Si existe un componente reutilizable debe utilizarse antes de crear uno nuevo.

---

## Compatibilidad

La misma identidad visual debe mantenerse en:

- versión Web
- futura aplicación Android
- modo escritorio
- dispositivos móviles

No crear dos diseños distintos.

Debe sentirse como una única aplicación adaptada a diferentes plataformas.

---

# 9. Cambio de Nombre del Proyecto

A partir de esta implementación, el nombre oficial del proyecto será:

# AnimeWing

Este cambio debe aplicarse de forma consistente en todo el proyecto, evitando referencias al nombre anterior cuando no sean necesarias.

## Cambios requeridos

Actualizar el nombre de la aplicación en todos los lugares donde corresponda, incluyendo, entre otros:

- Título del navegador (`document.title`).
- `<title>` del proyecto.
- `package.json`.
- `package-lock.json` (si corresponde).
- `manifest.json`.
- Configuración de la Progressive Web App (PWA).
- Nombre de la aplicación instalado en dispositivos.
- Nombre mostrado en Android.
- Splash Screen.
- Nombre de la aplicación en el Launcher.
- Configuración de Capacitor (si se utiliza).
- Configuración de Gradle (si corresponde).
- Configuración de Kotlin/Android (si corresponde).
- Nombre mostrado en los diálogos de instalación.
- Nombre utilizado en los metadatos de la aplicación.
- README.
- Documentación del proyecto.
- Pantallas donde aparezca el nombre de la aplicación.
- Cualquier texto visible para el usuario que haga referencia al nombre del proyecto.

## Identidad

El nombre **AnimeWing** debe utilizarse como nombre comercial de la aplicación.

Debe mantenerse la identidad visual definida anteriormente:

- Logo oficial:
  `C:\Users\Carlo\Documents\Proyectos\jkanime_vue\backend\media\PI_Wing_Zero_Mercy.webp`

- Paleta de colores Wing Zero Custom.

Toda la experiencia de usuario debe transmitir una identidad visual coherente entre el nombre **AnimeWing**, el logotipo y la paleta de colores.

## Compatibilidad

El cambio de nombre no debe afectar:

- rutas
- endpoints
- funcionamiento interno
- estructura del proyecto

Salvo que sea estrictamente necesario para la compilación o generación de la aplicación.

En caso de existir identificadores internos cuyo cambio pueda romper compatibilidad, conservarlos y modificar únicamente los elementos visibles para el usuario.

## Revisión final

Antes de finalizar la implementación:

- Verificar que no existan referencias visibles al nombre anterior.
- Verificar que el título del navegador muestre **AnimeWing**.
- Verificar que la aplicación Android se instale con el nombre **AnimeWing**.
- Verificar que el favicon y los íconos correspondan al logo oficial.
- Verificar que la identidad visual sea consistente en toda la aplicación.
---

# Objetivo final

El resultado debe ser un proyecto estable, mantenible y consistente con la arquitectura actual.

Antes de implementar cualquier cambio:

1. Analiza completamente el proyecto.
2. Identifica componentes reutilizables.
3. Reutiliza toda la lógica existente siempre que sea posible.
4. Evita duplicar código.
5. Mantén compatibilidad con futuras funcionalidades.
6. No modifiques comportamientos existentes que no hayan sido solicitados.