"""Script de diagnóstico: por qué fallan los servidores de un capítulo."""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from series.models import Capitulo
from series.scrapers import get_scraper
from series import server_stats
from series.tasks import _stream_from_server

cap_id = int(sys.argv[1])
cap = Capitulo.objects.select_related('serie').get(id=cap_id)
print(f"Capitulo {cap.numero} ({cap.nombre_archivo}) serie={cap.serie.nombre}")

s = get_scraper(cap.serie.fuente)
urls = s.get_download_urls(cap.url_fuente)
print(f"servidores encontrados: {len(urls)}")

candidatos = server_stats.rank(cap.serie.fuente, urls)
for info in candidatos:
    print(f"  - {info.get('server')} resolved={info.get('resolved')} url={info.get('url','')[:90]}")


def update_state(state, meta):
    print(f"    [{state}] {meta.get('fase','')} {meta.get('servidor','')} "
          f"{meta.get('descargado_str','')}/{meta.get('total_str','')} "
          f"{meta.get('porcentaje','')}%")


from pathlib import Path
tmp = Path(os.environ.get('TEMP', '.')) / 'debug_ep.mp4'
for info in candidatos:
    print(f"\n=== Probando {info.get('server')} ===")
    if tmp.exists():
        tmp.unlink()
    try:
        ok, nbytes = _stream_from_server(info, tmp, update_state, cap)
        print(f"    resultado: ok={ok} bytes={nbytes}")
    except Exception as e:
        print(f"    excepcion: {type(e).__name__}: {e}")
