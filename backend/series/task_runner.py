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

from django.conf import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Estado en memoria (thread-safe)
# ---------------------------------------------------------------------------

_tasks = {}  # {task_id: dict}
_tasks_lock = threading.Lock()
_cancel_flags = {}  # {task_id: bool}
_cancel_flags_lock = threading.Lock()
_verificacion_task_id = None  # solo una verificacion a la vez

# ---------------------------------------------------------------------------
# Cola de trabajos
# ---------------------------------------------------------------------------

download_queue = queue.Queue()

# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------


def enqueue_download(capitulo_id: int) -> str:
    """Encola descarga de un capitulo. Retorna task_id."""
    task_id = str(uuid.uuid4())
    _init_task(task_id, {
        'state': 'PENDING',
        'fase': '',
        'capitulo': '',
        'numero': 0,
        'serie': '',
        'slug': '',
        'servidor': '',
        'descargado': 0,
        'total': 0,
        'descargado_str': '0 B',
        'total_str': '0 B',
        'porcentaje': 0,
    })
    download_queue.put(('download', task_id, capitulo_id))
    return task_id


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
        capitulo = task.get('capitulo', '')
        if slug and capitulo:
            download_dir = Path(settings.DOWNLOAD_DIR)
            pattern = str(download_dir / slug / f"{Path(capitulo).stem}*.part")
            for part_file in glob.glob(pattern):
                try:
                    Path(part_file).unlink()
                    cleaned += 1
                except OSError:
                    pass
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
    from .tasks import _run_download, _run_descargar_todos, _run_verificar

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
