"""
Estado compartido a nivel de proceso para los scrapers.

Este modulo es deliberadamente "de proceso": las caches TTL y la sesion HTTP se
crean una sola vez al importarse, para que el camino de request (views) y los
workers en background (tasks) compartan exactamente el mismo estado en vez de
competir por la misma IP.

Tres piezas:

- `SCRAPE_CACHE`: cache TTL de 24h para la info de serie (`get_series_info`).
- `TRENDING_CACHE`: cache TTL de 30 min para el trending (`get_trending`).
- `shared_scraper_session()`: una sesion cloudscraper por clase scraper, para
  no re-resolver el desafio de Cloudflare en cada llamada a metodo. Las clases
  con `CF_CLEARANCE = True` reciben la sesion de `cf_clearance.py`, que mantiene
  la cookie `cf_clearance` (hoy obligatoria en jkanime: sin ella todo es 403).

Por que DOS caches y no una con TTL por clave: los dos datos quieren TTL
opuestos y compartian instancia, con el resultado de que la lista de "ultimos
episodios" se congelaba 24h (el server servia `Thunder 3 ep12` mientras un
scrape fresco daba `Dogulwang ep12`). El scrape real del trending se midio en
0.65s, asi que cachearlo 24h no ahorraba nada: solo bloqueaba el refresco
horario que el usuario quiere. Y `get_series_info` si necesita 24h, pero no por
performance sino por cortesia: existe para respetar el cooldown de
REFRESH_ESTADO_HORAS de `series/fuente.py`. Dos instancias con dos constantes
lo dicen sin logica condicional; un TTL por clave habria convertido el
`get_or_set` en un call site mas chico de lo que ya es.

Nota sobre el TTL de 24h: tiene que ser >= REFRESH_ESTADO_HORAS (24) de
`series/fuente.py`. Ese modulo importa `get_scraper` de este paquete, asi que
importar la constante desde alla seria circular; por eso vive duplicada aqui
como literal. Si se cambia REFRESH_ESTADO_HORAS, hay que actualizar
SCRAPE_CACHE_TTL_SEGUNDOS en este archivo.
"""
import copy
import threading
import time

import cloudscraper

from .cf_clearance import create_session as create_clearance_session


# Debe ser >= REFRESH_ESTADO_HORAS (24). Si el cache expirara antes que el
# cooldown, cada pagina re-scrapearia lo que el cooldown ya habia saltado, y la
# cache AUMENTARIA el trafico contra jkanime.net en vez de reducirlo.
SCRAPE_CACHE_TTL_SEGUNDOS = 24 * 3600

# 30 min para el trending. Suficiente para que N page loads seguidos no paguen
# el scrape de nuevo, y corto para que la lista no se vea congelada entre
# refreshes. La corrida horaria y el boton manual ni siquiera esperan a esto:
# piden `force=True` y siempre scrapean.
TRENDING_CACHE_TTL_SEGUNDOS = 30 * 60

# Espera maxima por un scrape que otro thread ya tiene en vuelo. Cubre el
# TIMEOUT del scraper (60s) mas el HEAD al CDN (~0.4s) medidos, con margen.
# Si se vence la espera, el thread hace su propio scrape en vez de quedar
# colgado: duplicar un request es peor que bloquear, pero no bloquear a
# perpetuo tambien.
SINGLE_FLIGHT_WAIT_SEGUNDOS = 90

# Techo de entradas vivas. Es holgado a proposito: las claves reales son
# (series + 1 trending). Existe solo para que un cardinality runaway (URLs
# distintas por request) no convierta la cache en una fuga de memoria.
MAX_CACHE_ENTRIES = 4096


def _is_cacheable(value) -> bool:
    """Decide si un resultado de scrape se puede guardar en la cache.

    Regla dura: solo se cachean resultados exitosos. `None` y `[]` significan
    que el scrape fallo, que Cloudflare no entrego contenido o que la pagina
    vino vacia; cachear cualquiera de esos casos congelaria el fallo por 24h
    y el usuario veria una lista vacia que no se arregla hasta que expire el
    TTL. El costo de no cachearlos es re-intentar en la proxima llamada.
    """
    return bool(value)


class _KeyLock:
    """Lock por clave con contador de referencias.

    El refcount existe para poder borrar la entrada del registro sin romper el
    single-flight: mientras un thread tenga una referencia, la entrada sigue en
    el dict, asi que ningun thread nuevo puede crear un lock distinto para la
    misma clave mientras el otro espera.
    """

    __slots__ = ("lock", "refs")

    def __init__(self):
        self.lock = threading.Lock()
        self.refs = 0


class TTLCache:
    """Cache en memoria con TTL, compartida por todos los threads del proceso.

    `get_or_set(key, producer)` devuelve el valor cacheado si esta vigente, y si
    no, lo produce UNA sola vez aunque muchos threads pidan la misma clave al
    mismo tiempo (single-flight). `producer` se ejecuta FUERA del lock global,
    asi que la cache no bloquea el resto de las claves.
    """

    def __init__(
        self,
        ttl_seconds,
        single_flight_wait_seconds=0.0,
        max_entries=MAX_CACHE_ENTRIES,
    ):
        self._ttl = float(ttl_seconds)
        self._single_flight_wait = float(single_flight_wait_seconds)
        self._max_entries = int(max_entries)
        self._lock = threading.Lock()
        self._entries = {}    # key -> (expira_en, valor)
        self._key_locks = {}  # key -> _KeyLock
        self._hits = 0
        self._misses = 0

    @property
    def ttl_seconds(self):
        return self._ttl

    def get_or_set(self, key, producer, force=False):
        """Devuelve el valor de `key`, produciendolo si no esta en cache.

        `producer` es un callable sin argumentos que hace el scrape real. Solo
        su resultado exitoso queda cacheado; si devuelve algo falsy, se devuelve
        al caller pero NO se guarda.

        `force=True` saltea la lectura y llama a `producer` siempre, renovando la
        entrada. Es lo que necesitan la tarea horaria y el boton manual: una
        corrida forzada jamas puede devolver cache, que es justamente el motivo
        por el que existen. El single-flight se mantiene (dos forzados se
        serializan por el lock de la clave) pero el re-chequeo se saltea, asi
        que cada corrida forzada scrapea de verdad.
        """
        if not force:
            value = self.get(key)
            if value is not None:
                return value

        key_lock = self._acquire_key_lock(key)
        try:
            acquired = key_lock.lock.acquire(timeout=self._single_flight_wait)
            if not acquired:
                # Otro thread lleva demasiado tiempo con este scrape.
                return producer()

            try:
                # Re-chequear: el thread que gano el lock puede haber llenado
                # la cache mientras este esperaba.
                if not force:
                    value = self.get(key)
                    if value is not None:
                        return value

                value = producer()  # red aqui, fuera de self._lock
                self.set(key, value)
                return value
            finally:
                key_lock.lock.release()
        finally:
            self._release_key_lock(key, key_lock)

    def get(self, key):
        """Devuelve una copia del valor cacheado, o None si no esta vigente."""
        ahora = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._misses += 1
                return None

            expira, valor = entry
            if expira <= ahora:
                del self._entries[key]
                self._misses += 1
                return None

            self._hits += 1
            # Copia defensiva: el cache es compartido por todos los threads y
            # ningun caller deberia poder mutar lo que hay guardado.
            return copy.deepcopy(valor)

    def set(self, key, value):
        """Guarda `value` si es cacheable. Devuelve True si se guardo."""
        if not _is_cacheable(value):
            return False

        with self._lock:
            self._make_room_locked()
            self._entries[key] = (
                time.monotonic() + self._ttl,
                copy.deepcopy(value),
            )
            return True

    def clear(self):
        with self._lock:
            self._entries.clear()

    def invalidate(self, key):
        """Borra una entrada. Devuelve True si habia algo que borrar.

        Ignora el TTL a proposito: el uso es "esta fuente cambio, no me devuelvas
        lo que guardaste", no "expiro". No toca el registro de locks: una entrada
        borrada con un `get_or_set` en vuelo la repone ese mismo thread al
        terminar, que es el comportamiento correcto para single-flight.
        """
        with self._lock:
            return self._entries.pop(key, None) is not None

    def stats(self):
        with self._lock:
            return {
                "entries": len(self._entries),
                "key_locks": len(self._key_locks),
                "hits": self._hits,
                "misses": self._misses,
                "ttl_seconds": self._ttl,
            }

    # -- internos ------------------------------------------------------

    def _make_room_locked(self):
        """Pura entradas vencidas y, si no alcanza, la que expira antes."""
        ahora = time.monotonic()
        vencidas = [k for k, (expira, _) in self._entries.items() if expira <= ahora]
        for k in vencidas:
            del self._entries[k]

        while len(self._entries) >= self._max_entries:
            soonest = min(self._entries, key=lambda k: self._entries[k][0])
            del self._entries[soonest]

    def _acquire_key_lock(self, key):
        with self._lock:
            key_lock = self._key_locks.get(key)
            if key_lock is None:
                key_lock = _KeyLock()
                self._key_locks[key] = key_lock
            key_lock.refs += 1
            return key_lock

    def _release_key_lock(self, key, key_lock):
        with self._lock:
            current = self._key_locks.get(key)
            if current is None:
                return
            current.refs -= 1
            if current.refs <= 0 and current is key_lock:
                del self._key_locks[key]


# Modulo-level a proposito: las comparten el path de request y los workers, que
# es justamente el punto (dejar de scrapear lo mismo dos veces por la misma IP).
# Son DOS instancias y no una con TTL por clave a proposito: ver el docstring.
SCRAPE_CACHE = TTLCache(
    ttl_seconds=SCRAPE_CACHE_TTL_SEGUNDOS,
    single_flight_wait_seconds=SINGLE_FLIGHT_WAIT_SEGUNDOS,
)

TRENDING_CACHE = TTLCache(
    ttl_seconds=TRENDING_CACHE_TTL_SEGUNDOS,
    single_flight_wait_seconds=SINGLE_FLIGHT_WAIT_SEGUNDOS,
)


def shared_scraper_session(owner):
    """Devuelve la sesion cloudscraper compartida por `owner`, creandola una vez.

    `owner` es la clase scraper; debe declarar `_session` (None) y
    `_session_lock`. Guardarla en la clase y no en la instancia la deja viva a
    nivel de proceso, aunque alguien construya el scraper a mano en vez de
    pasar por `get_scraper()`.

    Reutilizar la sesion es lo que evita pagar el handshake con Cloudflare en
    cada llamada: cada sesion nueva lo empieza desde cero, y la misma URL se
    midio entre 1.48s y 49.43s segun si la sesion estaba caliente o no.

    Las fuentes que declaren `CF_CLEARANCE = True` reciben ademas la cookie
    `cf_clearance` que Chrome obtiene en `cf_clearance.py`. Sin ella jkanime
    responde 403 a todo: su Cloudflare hoy sirve un Managed Challenge, que
    cloudscraper no resuelve (ver el docstring de ese modulo).

    Levanta TypeError si `_session` resulto ser otra cosa. `_session` se resuelve
    por atributo, asi que una clase que declare un `@property`, un
    `@contextmanager` o un metodo con ese nombre devuelve ESA cosa y no una
    sesion: sin este chequeo el caller recibe un objeto que no sabe usar y el
    error aflora mas tarde, en otro archivo, con otro mensaje. Que el error
    nombre a la clase es el punto.
    """
    session = owner._session
    if session is None:
        with owner._session_lock:
            session = owner._session
            if session is None:
                if getattr(owner, "CF_CLEARANCE", False):
                    session = create_clearance_session(user_agent=owner.USER_AGENT)
                else:
                    session = cloudscraper.create_scraper(
                        browser={"custom": owner.USER_AGENT}
                    )
                owner._session = session

    if not isinstance(session, cloudscraper.CloudScraper):
        raise TypeError(
            f"{owner.__name__}._session es {type(session).__name__}, no una sesion "
            f"de cloudscraper. Esta clase no debe pasar por "
            f"shared_scraper_session: o declara `_session = None` y `_session_lock` "
            f"como atributos de clase, o —si la sesion es privada por diseno— no "
            f"usa este helper."
        )
    return session
