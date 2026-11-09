"""
Cola de tareas con threading: reemplazo de Celery + Redis.

Arranca N workers daemon que procesan descargas y verificacion
desde una queue.Queue FIFO. El estado se guarda en memoria con
un dict compartido (thread-safe via Lock).
"""

import glob
import logging
import queue
import threading
import uuid
from pathlib import Path

from .paths import serie_download_dir

logger = logging.getLogger(__name__)


class TaskCancelled(Exception):
    """Cooperative cancellation signal for a running task.

    Raised by a task's `update_state` callback once `cancel_task()` has set its
    flag. The download chain must let it propagate instead of swallowing it in a
    broad `except Exception`, so the worker aborts the in-flight transfer and
    its `finally` can release the in-flight chapter slot.

    It is a dedicated exception and NOT `StopIteration`: PEP 479 turns a
    `StopIteration` raised inside a generator into a `RuntimeError`, so if the
    signal ever crosses a generator the cancellation would be turned into a
    crash instead of a clean abort.
    """


# ---------------------------------------------------------------------------
# Estado en memoria (thread-safe)
# ---------------------------------------------------------------------------

_tasks = {}  # {task_id: dict}
_tasks_lock = threading.Lock()
_cancel_flags = {}  # {task_id: bool}
_cancel_flags_lock = threading.Lock()
_verificacion_task_id = None  # solo una verificacion a la vez
_estados_task_id = None  # solo una revalidacion de estados a la vez
_trending_task_id = None  # solo una sincronizacion de trending a la vez

# Capitulos con una descarga en vuelo (PENDING o PROGRESS). Sin esto, dos
# enqueue para el mismo capitulo (doble click, race de restoreFromServer,
# descargar-todos solapado con una descarga individual) levantan dos workers que
# escriben el MISMO Episodio-N.part a la vez y lo corrompen. Mapa
# {capitulo_id: task_id}: el task_id es el dueno del slot y es la UNICA
# autoridad. Solo lo libera `release_download()` desde el `finally` del worker
# dueno, cuando ese worker ya salio de verdad; `enqueue_download()` /
# `try_register_download()` nunca le roban el slot a otro.
_in_flight_capitulos = {}
_in_flight_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Cola de trabajos
# ---------------------------------------------------------------------------

download_queue = queue.Queue()

# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------


def enqueue_download(capitulo_id: int) -> str:
    """Encola descarga de un capitulo. Retorna task_id.

    Deduplica por capitulo: si ya hay una descarga en vuelo para el, devuelve ese
    task_id en vez de encolar una segunda. El slot en vuelo es la unica
    autoridad: solo lo libera `release_download()` desde el `finally` del worker
    dueno. A proposito NO se consulta `_tasks` para decidir si el slot esta vivo:
    `cancel_task()` saca la tarea de `_tasks` mientras su worker sigue vivo, y
    tratar ese estado como "slot libre" levantaba un SEGUNDO worker sobre el
    mismo `.part` (la corrupcion que este mapa existe para evitar).
    """
    with _in_flight_lock:
        existing = _in_flight_capitulos.get(capitulo_id)
        if existing:
            # A live owner is still writing this chapter: reuse its task instead
            # of starting a second writer. The slot is released only when that
            # worker exits (see `release_download`).
            return existing

        task_id = str(uuid.uuid4())
        _init_task(task_id, {
            'state': 'PENDING',
            'fase': '',
            'capitulo': '',
            'numero': 0,
            'serie': '',
            'slug': '',
            'fuente': '',
            'servidor': '',
            'capitulo_id': capitulo_id,
            'descargado': 0,
            'total': 0,
            'descargado_str': '0 B',
            'total_str': '0 B',
            'porcentaje': 0,
        })
        _in_flight_capitulos[capitulo_id] = task_id
        download_queue.put(('download', task_id, capitulo_id))
    return task_id


def try_register_download(capitulo_id: int, task_id: str) -> bool:
    """Reclama el slot en vuelo de `capitulo_id` para `task_id`.

    Returns True if the slot was claimed; False if a DIFFERENT task already
    holds it. The bulk download (`_run_descargar_todos`) uses it to skip chapters
    already being downloaded and to avoid overlapping an individual download.

    The slot is the sole authority: it is freed only by the owning worker's
    `finally`, so any other owner means "still writing" and must be respected.
    """
    with _in_flight_lock:
        existing = _in_flight_capitulos.get(capitulo_id)
        if existing and existing != task_id:
            return False
        _in_flight_capitulos[capitulo_id] = task_id
        return True


def release_download(capitulo_id: int, task_id: str) -> None:
    """Libera el slot en vuelo si todavia pertenece a `task_id`.

    Idempotente: si el capitulo se re-encolo con otro task_id, un worker viejo
    no le borra el registro al nuevo.
    """
    with _in_flight_lock:
        if _in_flight_capitulos.get(capitulo_id) == task_id:
            _in_flight_capitulos.pop(capitulo_id, None)


def enqueue_descargar_todos(serie_id: int) -> str:
    """Encola descarga de todos los capitulos faltantes de una serie."""
    task_id = str(uuid.uuid4())
    _init_task(task_id, {
        'state': 'PENDING',
        'fase': 'iniciando',
        'mensaje': 'Preparando descargas...',
        'total_capitulos': 0,
        'completados': 0,
        'fallidos': 0,
    })
    download_queue.put(('descargar_todos', task_id, serie_id))
    return task_id


def enqueue_verificar() -> str | None:
    """Encola verificacion. Solo una a la vez. Retorna task_id o None si ya corre."""
    global _verificacion_task_id
    if _verificacion_task_id:
        task = get_task(_verificacion_task_id)
        if task and task.get('state') in ('PENDING', 'PROGRESS'):
            return None

    task_id = str(uuid.uuid4())
    _verificacion_task_id = task_id
    _init_task(task_id, {
        'state': 'PENDING',
        'fase': '',
        'mensaje': 'En cola...',
        'indice': 0,
        'total': 0,
    })
    download_queue.put(('verificar', task_id, None))
    return task_id


def enqueue_verificar_estados() -> str | None:
    """Encola revalidacion de estado/dia_emision (solo series en_emision).

    Solo una a la vez. Retorna task_id o None si ya corre.
    """
    global _estados_task_id
    if _estados_task_id:
        task = get_task(_estados_task_id)
        if task and task.get('state') in ('PENDING', 'PROGRESS'):
            return None

    task_id = str(uuid.uuid4())
    _estados_task_id = task_id
    _init_task(task_id, {
        'state': 'PENDING',
        'fase': '',
        'mensaje': 'En cola...',
        'indice': 0,
        'total': 0,
        'reverificadas': 0,
    })
    download_queue.put(('verificar_estados', task_id, None))
    return task_id


def enqueue_verificar_trending() -> str | None:
    """Encola la sincronizacion del trending (capitulos nuevos). Solo una a la vez.

    Corre la misma escritura en BD que `api_ultimos_episodios`, pero con scrape
    forzado: el endpoint se sirve de la cache de 30 min del trending y esta tarea
    existe para no depender de ese TTL. El frontend la dispara cada hora y con el
    boton manual.

    Retorna task_id o None si ya corre.
    """
    global _trending_task_id
    if _trending_task_id:
        task = get_task(_trending_task_id)
        if task and task.get('state') in ('PENDING', 'PROGRESS'):
            return None

    task_id = str(uuid.uuid4())
    _trending_task_id = task_id
    _init_task(task_id, {
        'state': 'PENDING',
        'fase': '',
        'mensaje': 'En cola...',
        'indice': 0,
        'total': 0,
        'nuevos': 0,
    })
    download_queue.put(('verificar_trending', task_id, None))
    return task_id


def get_task(task_id: str) -> dict | None:
    with _tasks_lock:
        return _tasks.get(task_id)


def get_active_tasks() -> list[dict]:
    with _tasks_lock:
        return [
            {**t, 'task_id': tid}
            for tid, t in _tasks.items()
            if t.get('state') in ('PENDING', 'PROGRESS')
        ]


def cancel_task(task_id: str) -> int:
    """Cancela tarea y limpia .part files. Retorna cantidad de archivos limpiados."""
    with _cancel_flags_lock:
        _cancel_flags[task_id] = True

    task = get_task(task_id)
    cleaned = 0
    if task:
        slug = task.get('slug', '')
        fuente = task.get('fuente', '')
        capitulo = task.get('capitulo', '')
        # La carpeta es `<fuente>-<slug>`: sin fuente NO se puede resolver, y
        # `serie_download_dir` la exige. Sin los dos datos se omite la limpieza
        # de `.part` en vez de arriesgar borrar en la carpeta equivocada.
        if slug and fuente and capitulo:
            download_dir = serie_download_dir(slug, fuente)
            pattern = str(download_dir / f"{Path(capitulo).stem}*.part")
            for part_file in glob.glob(pattern):
                try:
                    Path(part_file).unlink()
                    cleaned += 1
                except OSError:
                    pass
        # The in-flight slot is deliberately NOT released here: the worker may
        # still be writing this chapter. It is released by the owning worker's
        # `finally` (tasks.py:_run_download), which runs only after the worker
        # has actually exited. Releasing it here would free the slot while a
        # second worker could start on the same `.part`.
    remove_task(task_id)
    return cleaned


def remove_task(task_id: str):
    with _tasks_lock:
        _tasks.pop(task_id, None)


def is_cancelled(task_id: str) -> bool:
    with _cancel_flags_lock:
        return _cancel_flags.get(task_id, False)


# ---------------------------------------------------------------------------
# Internas
# ---------------------------------------------------------------------------


def _init_task(task_id: str, default: dict):
    with _tasks_lock:
        _tasks[task_id] = {'task_id': task_id, **default}


def update_task(task_id: str, **kwargs):
    with _tasks_lock:
        if task_id in _tasks:
            _tasks[task_id].update(kwargs)


# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------


def _worker_loop():
    """Loop principal del worker. Saca trabajos de la cola y los ejecuta."""
    from .tasks import (
        _run_descargar_todos,
        _run_download,
        _run_verificar,
        _run_verificar_estados,
        _run_verificar_trending,
    )

    while True:
        try:
            action, task_id, payload = download_queue.get()
            try:
                if action == 'download':
                    _run_download(task_id, payload)
                elif action == 'descargar_todos':
                    _run_descargar_todos(task_id, payload)
                elif action == 'verificar':
                    _run_verificar(task_id)
                elif action == 'verificar_estados':
                    _run_verificar_estados(task_id)
                elif action == 'verificar_trending':
                    _run_verificar_trending(task_id)
                elif action == 'youtube':
                    from .tasks import _run_youtube_download
                    _run_youtube_download(task_id, payload['video_url'], payload['capitulo_numero'], payload['capitulo_title'])
            except Exception as e:
                logger.exception(f"Error inesperado en tarea {task_id}: {e}")
                update_task(task_id, state='FAILURE', message=str(e))
            finally:
                download_queue.task_done()
        except Exception as e:
            logger.exception(f"Error en worker loop: {e}")


def start_workers(count: int = 10):
    """Levanta N workers daemon."""
    for i in range(count):
        t = threading.Thread(target=_worker_loop, daemon=True, name=f"worker-{i}")
        t.start()
    logger.info(f"Task runner iniciado con {count} workers")
