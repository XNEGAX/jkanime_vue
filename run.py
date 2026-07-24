import os
import sys
import subprocess
import time
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DJANGO_DIR = BASE_DIR / 'backend'
VENV_PYTHON = BASE_DIR / 'venv' / 'Scripts' / 'python.exe'

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ['PYTHONPATH'] = str(DJANGO_DIR)


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


def main():
    print("============================================")
    print("   Jkanime Vue - Gestor de Series")
    print("============================================")
    print()

    print("[1/2] Limpiando procesos anteriores...")
    kill_process_on_port(8000)
    time.sleep(1)
    print()

    webbrowser.open('http://127.0.0.1:8000')

    print("[2/2] Iniciando Django...")
    print()
    print("============================================")
    print("   Servidor en http://127.0.0.1:8000")
    print("   10 workers de descarga (via AppConfig.ready)")
    print("   Presione Ctrl+C para detener")
    print("============================================")
    print()

    try:
        subprocess.run(
            [str(VENV_PYTHON), 'manage.py', 'makemigrations'],
            cwd=str(DJANGO_DIR),
        )
        subprocess.run(
            [str(VENV_PYTHON), 'manage.py', 'migrate'],
            cwd=str(DJANGO_DIR),
        )
        subprocess.run(
            [str(VENV_PYTHON), 'manage.py', 'runserver', '0.0.0.0:8000'],
            cwd=str(DJANGO_DIR),
        )
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
