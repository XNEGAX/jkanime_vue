import os
import sys
import subprocess
import time
import signal
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DJANGO_DIR = BASE_DIR / 'jkanime_vue'
VENV_PYTHON = BASE_DIR / 'venv' / 'Scripts' / 'python.exe'
LOG_DIR = BASE_DIR / 'logs'

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jkanime_vue.settings')
os.environ['PYTHONPATH'] = str(DJANGO_DIR)

celery_procs = []


def find_redis_server():
    import shutil
    redis = shutil.which('redis-server')
    if redis:
        return redis
    local_appdata = os.environ.get('LOCALAPPDATA', '')
    for f in Path(local_appdata, 'Microsoft', 'WinGet', 'Packages').rglob('redis-server.exe'):
        return str(f)
    for path in ['C:\\Program Files\\Redis\\redis-server.exe']:
        if Path(path).exists():
            return path
    return None


def is_redis_running():
    try:
        import redis as r
        r.Redis(host='127.0.0.1', port=6379, socket_connect_timeout=2).ping()
        return True
    except Exception:
        return False


def start_redis():
    rpath = find_redis_server()
    if not rpath:
        print("  [ERROR] Redis no encontrado. Instalalo con: winget install taizod1024.redis-windows-fork")
        sys.exit(1)
    print(f"  Iniciando Redis desde: {rpath}")
    subprocess.Popen(
        [rpath, '--port', '6379'],
        creationflags=subprocess.CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(3)


def kill_process_on_port(port):
    result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if f':{port}' in line and 'LISTENING' in line:
            pid = line.strip().split()[-1]
            try:
                subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
                print(f"  Deteniendo proceso anterior en puerto {port} (PID {pid})")
            except Exception:
                pass


def kill_celery_workers():
    for title in ['*Celery*', '*celery*', '*Descargas*', '*Actualizaciones*']:
        subprocess.run(['taskkill', '/F', '/FI', f'WINDOWTITLE eq {title}'], capture_output=True)
    subprocess.run(['taskkill', '/F', '/IM', 'python.exe', '/FI', 'WINDOWTITLE eq *Celery*'], capture_output=True)


def start_celery(name, queue, pool, concurrency, log_file):
    log_path = LOG_DIR / log_file
    log_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(VENV_PYTHON), '-m', 'celery', '-A', 'jkanime_vue', 'worker',
        '--loglevel=info', f'--pool={pool}', f'--concurrency={concurrency}',
        f'--queues={queue}', f'--hostname={name}@%h',
    ]
    with open(log_path, 'a') as f:
        p = subprocess.Popen(
            cmd, cwd=str(DJANGO_DIR),
            stdout=f, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    return p


def main():
    print("============================================")
    print("   Jkanime Vue - Gestor de Series")
    print("============================================")
    print()

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    print("[1/4] Verificando Redis...")
    if is_redis_running():
        print("  Redis ya esta corriendo en puerto 6379.")
    else:
        start_redis()
        if is_redis_running():
            print("  Redis iniciado correctamente.")
        else:
            print("  [ERROR] Redis no responde despues de iniciar.")
            sys.exit(1)
    print()

    print("[2/4] Limpiando procesos anteriores...")
    kill_process_on_port(8000)
    kill_celery_workers()
    time.sleep(1)
    print()

    print("[3/4] Iniciando Celery workers...")

    print("  Iniciando Celery worker: descargas (gevent x10)...")
    p1 = start_celery('descargas', 'descargas', 'gevent', 10, 'celery_descargas.log')
    celery_procs.append(p1)
    time.sleep(3)

    print("  Iniciando Celery worker: actualizaciones (solo x1)...")
    p2 = start_celery('actualizaciones', 'actualizaciones', 'solo', 1, 'celery_actualizaciones.log')
    celery_procs.append(p2)
    time.sleep(3)
    print()

    webbrowser.open('http://127.0.0.1:8000')

    print("[4/4] Iniciando Django...")
    print()
    print("============================================")
    print("   Servidor en http://127.0.0.1:8000")
    print("   Celery: descargas x10 | actualizaciones x1")
    print("   Presione Ctrl+C para detener")
    print("============================================")
    print()

    try:
        subprocess.run(
            [str(VENV_PYTHON), 'manage.py', 'runserver', '0.0.0.0:8000'],
            cwd=str(DJANGO_DIR),
        )
    except KeyboardInterrupt:
        pass
    finally:
        print("\n  Deteniendo servicios...")
        for p in celery_procs:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == '__main__':
    main()
