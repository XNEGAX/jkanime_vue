"""
Cookie `cf_clearance` de Cloudflare para jkanime.net.

Por que existe este modulo
--------------------------
jkanime.net esta detras de un **Managed Challenge** de Cloudflare
(`cType: managed`, verificado en el HTML del 403). Eso NO es el challenge JS
legacy (IUAM) que sabe resolver `cloudscraper`: hoy toda peticion sin navegador
recibe `403` con `<title>Just a moment...</title>`, y como cada metodo del
scraper atrapa la excepcion y devuelve `[]` / `None`, el sintoma es "la lista de
ultimos episodios sale vacia" y "no descarga nada".

Se probo lo que suele recomendarse y no alcanza:

- `cloudscraper` 1.2.71 (con UA custom y con el default): 403.
- `curl_cffi` impersonando Chrome 124 / 131 / Safari (mismo fingerprint TLS que
  un Chrome real): 403. O sea no es solo el fingerprint TLS.
- Playwright lanzando el navegador el mismo (`headless=True`, `headless=False`,
  con UA real, con ventana fuera de pantalla): el Turnstile invisible se queda
  girando para siempre. Cloudflare detecta los flags de automatizacion.
- Leer la cookie del perfil de Chrome del usuario: las cookies estan cifradas
  con App-Bound Encryption (`v20`), que no se descifra sin herramientas
  elevadas. Descartado.

Lo que si funciona, medido: lanzar el Chrome REAL del usuario como proceso
normal (sin flags de automatizacion), conectarse por CDP y navegar. El challenge
pasa en ~4s, Cloudflare emite `cf_clearance` con vencimiento de ~1 anio, y desde
ahi la cookie sirve para `requests`/`cloudscraper` con la misma IP y el mismo
User-Agent.

Por eso `ClearanceCloudScraper` existe: mantiene la cookie aplicada a la sesion,
fija el UA EXACTO del Chrome que la obtuvo (la cookie esta atada a IP + UA) y,
si igual recibe 403, renueva la cookie una vez y reintenta.

La ventana de Chrome se abre fuera de pantalla (`--window-position=-32000,...`)
en vez de en modo headless: headless no pasa el challenge, y esto no molesta.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import logging
import os
import shutil
import socket
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import cloudscraper

logger = logging.getLogger(__name__)

# backend/ — este archivo vive en backend/series/scrapers/.
BASE_DIR = Path(__file__).resolve().parents[2]
STATE_DIR = BASE_DIR / ".cf_clearance"
STATE_FILE = STATE_DIR / "state.json"
PROFILE_DIR = STATE_DIR / "chrome-profile"

SITE_URL = "https://jkanime.net/"
COOKIE_DOMAIN_SUFFIX = "jkanime.net"

# Cuanto se espera a que Cloudflare entregue la cookie. Medido: ~4s con la
# sesion de Chrome ya caliente, ~20s con un perfil nuevo. 90s deja margen para
# una maquina lenta sin colgar un worker 10 minutos si Cloudflare decidio no
# pasar el challenge.
CHALLENGE_TIMEOUT_SEGUNDOS = 90

# Cuanto se espera a que Chrome abra el puerto de CDP.
CDP_START_TIMEOUT_SEGUNDOS = 40

# Techo de vida util que le damos a la cookie en disco, aunque Cloudflare le
# ponga un anio: si la IP cambia (reinicio del router) o Cloudflare revoca la
# cookie, el reintento por 403 la renueva. 12h evita relanzar Chrome en cada
# arranque de la app sin confiar en una cookie vieja para siempre.
MAX_FRESH_SEGUNDOS = 12 * 3600

# Si dos threads reciben 403 al mismo tiempo, el segundo NO relanza Chrome:
# reusa la cookie que el primero acaba de traer. Chrome tarda ~5s y abrir dos
# ventanas en paralelo ademas pelea por el mismo perfil.
MIN_REFRESH_INTERVALO_SEGUNDOS = 20

_CHROME_CANDIDATOS = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
)

_lock = threading.Lock()
_current: "Clearance | None" = None
_chrome_on_403 = threading.local()


@contextmanager
def allow_chrome_on_403():
    """Permite resolver Cloudflare con Chrome solo dentro del contexto actual."""
    previous = getattr(_chrome_on_403, "enabled", False)
    _chrome_on_403.enabled = True
    try:
        yield
    finally:
        _chrome_on_403.enabled = previous


def _can_launch_chrome() -> bool:
    return getattr(_chrome_on_403, "enabled", False)


class ClearanceError(RuntimeError):
    """No se pudo obtener la cookie `cf_clearance`."""


@dataclass
class Clearance:
    """Cookies de jkanime + User-Agent del navegador que las obtuvo."""

    cookies: list[dict]
    user_agent: str
    obtained_at: float
    expires_at: float

    def is_fresh(self, now: float | None = None) -> bool:
        ahora = time.time() if now is None else now
        return ahora < self.expires_at

    def to_json(self) -> dict:
        return {
            "cookies": self.cookies,
            "user_agent": self.user_agent,
            "obtained_at": self.obtained_at,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_json(cls, data: dict) -> "Clearance":
        return cls(
            cookies=list(data["cookies"]),
            user_agent=str(data["user_agent"]),
            obtained_at=float(data["obtained_at"]),
            expires_at=float(data["expires_at"]),
        )


def get_clearance(force: bool = False) -> Clearance:
    """Devuelve la cookie vigente, obteniendola con Chrome si hace falta.

    `force=True` la renueva aunque parezca vigente: es el camino del reintento
    por 403, o sea "Cloudflare la rechazo, no me sirve la de memoria".
    """
    global _current

    if not force and _current is not None and _current.is_fresh():
        return _current

    with _lock:
        # Doble chequeo: otro thread pudo renovarla mientras esperabamos el lock.
        if _current is not None:
            if not force and _current.is_fresh():
                return _current
            if force and (time.time() - _current.obtained_at) < MIN_REFRESH_INTERVALO_SEGUNDOS:
                return _current

        if not force:
            en_disco = _load_state()
            if en_disco is not None and en_disco.is_fresh():
                _current = en_disco
                return en_disco

        logger.info("Obteniendo cf_clearance de jkanime con Chrome (CDP)...")
        t0 = time.time()
        clearance = _fetch_clearance()
        logger.info(
            "cf_clearance obtenida en %.1fs (UA=%s)", time.time() - t0, clearance.user_agent
        )
        _current = clearance
        _save_state(clearance)
        return clearance


def get_cached_clearance() -> "Clearance | None":
    """Devuelve una cookie vigente sin lanzar Chrome si no hay estado válido."""
    global _current

    if _current is not None and _current.is_fresh():
        return _current

    with _lock:
        if _current is not None and _current.is_fresh():
            return _current
        en_disco = _load_state()
        if en_disco is not None and en_disco.is_fresh():
            _current = en_disco
            return en_disco
    return None


def invalidate() -> None:
    """Olvida la cookie en memoria y en disco. No borra el perfil de Chrome."""
    global _current
    with _lock:
        _current = None
        try:
            STATE_FILE.unlink()
        except FileNotFoundError:
            pass


def create_session(user_agent: str | None = None) -> "ClearanceCloudScraper":
    """Crea la sesion que mantiene la cookie aplicada. Usada por cache.py."""
    return ClearanceCloudScraper(user_agent=user_agent)


class ClearanceCloudScraper(cloudscraper.CloudScraper):
    """`CloudScraper` que aplica y renueva `cf_clearance` automaticamente.

    Es subclase de `CloudScraper` a proposito: `shared_scraper_session` valida
    `isinstance(session, cloudscraper.CloudScraper)` y el resto del codigo usa la
    sesion como una sesion de requests cualquiera (`get`, `post`, `head`).
    """

    def __init__(self, *args, user_agent: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        # UA de respaldo: el real lo impone la cookie cuando llega, porque
        # cf_clearance solo vale para el UA exacto del navegador que la obtuvo.
        if user_agent:
            self.headers["User-Agent"] = user_agent
        self._clearance: Clearance | None = None

    # -- API de requests -------------------------------------------------
    def request(self, method, url, *args, **kwargs):
        clearance = self._clearance
        if clearance is None or not clearance.is_fresh():
            clearance = get_cached_clearance()
            self._clearance = clearance
        if clearance is not None:
            self._apply(clearance)

        response = super().request(method, url, *args, **kwargs)

        # 403 con la cookie aplicada = Cloudflare la revoco (IP nueva, cambio de
        # UA, o expiro antes de lo que decia). Un solo reintento: si el segundo
        # tambien falla, el problema no es la cookie y reintentar solo suma
        # trafico contra el sitio.
        if response.status_code == 403 and _can_launch_chrome():
            fresca = self._obtain(force=True)
            if fresca is not None and fresca is not clearance:
                logger.warning("403 de %s: reintentando con cf_clearance renovada", url)
                self._apply(fresca)
                response = super().request(method, url, *args, **kwargs)

        return response

    # -- internos --------------------------------------------------------
    def _obtain(self, force: bool) -> Clearance | None:
        try:
            clearance = get_clearance(force=force)
        except ClearanceError as exc:
            # Sin cookie la sesion sigue siendo usable (latanime, CDN, otros
            # hosts): no se levanta, se loguea una vez y el caller ve el 403.
            logger.error("Sin cf_clearance para jkanime: %s", exc)
            return None
        self._clearance = clearance
        return clearance

    def _apply(self, clearance: Clearance) -> None:
        self.headers["User-Agent"] = clearance.user_agent
        for cookie in clearance.cookies:
            nombre = cookie.get("name")
            if not nombre:
                continue
            self.cookies.set(
                nombre,
                cookie.get("value", ""),
                domain=cookie.get("domain") or None,
                path=cookie.get("path") or "/",
            )


# ----------------------------------------------------------------------
#  Obtencion con Chrome real via CDP
# ----------------------------------------------------------------------

def _find_chrome() -> str | None:
    """Ruta al navegador a usar. `CHROME_PATH` gana para poder apuntar a otro."""
    override = os.environ.get("CHROME_PATH")
    if override:
        if Path(override).exists():
            return override
        logger.warning("CHROME_PATH=%s no existe, se busca el navegador por defecto", override)

    for candidato in _CHROME_CANDIDATOS:
        if Path(candidato).exists():
            return candidato

    for nombre in ("chrome", "msedge", "chromium", "google-chrome"):
        encontrado = shutil.which(nombre)
        if encontrado:
            return encontrado
    return None


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _fetch_clearance() -> Clearance:
    chrome = _find_chrome()
    if chrome is None:
        raise ClearanceError(
            "no se encontro Chrome/Edge. Instalalo o define CHROME_PATH con la ruta al ejecutable"
        )

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise ClearanceError(
            "falta el paquete playwright (pip install playwright). No hace falta "
            "`playwright install`: se usa el Chrome ya instalado via CDP"
        ) from exc

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    port = _free_port()
    proceso = subprocess.Popen(
        [
            chrome,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={PROFILE_DIR}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-blink-features=AutomationControlled",
            # Fuera de pantalla: headless NO pasa el challenge, pero una ventana
            # visible cada 12h tampoco es aceptable.
            "--window-position=-32000,-32000",
            "--window-size=1000,800",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        _wait_for_cdp(port, proceso)
        return _harvest(port, sync_playwright)
    finally:
        proceso.terminate()
        try:
            proceso.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover
            proceso.kill()


def _wait_for_cdp(port: int, proceso: subprocess.Popen) -> None:
    import urllib.error
    import urllib.request

    limite = time.time() + CDP_START_TIMEOUT_SEGUNDOS
    url = f"http://127.0.0.1:{port}/json/version"
    while time.time() < limite:
        if proceso.poll() is not None:
            raise ClearanceError(
                f"Chrome termino con codigo {proceso.returncode} antes de abrir CDP"
            )
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except (urllib.error.URLError, OSError):
            time.sleep(0.3)
    raise ClearanceError(
        f"Chrome no abrio el puerto CDP {port} en {CDP_START_TIMEOUT_SEGUNDOS}s"
    )


def _harvest(port: int, sync_playwright) -> Clearance:
    """Navega a jkanime con el Chrome ya abierto y cosecha las cookies."""
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        try:
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(SITE_URL, wait_until="domcontentloaded", timeout=CHALLENGE_TIMEOUT_SEGUNDOS * 1000)

            limite = time.time() + CHALLENGE_TIMEOUT_SEGUNDOS
            cookies: list[dict] = []
            while time.time() < limite:
                cookies = [
                    dict(c) for c in context.cookies()
                    if COOKIE_DOMAIN_SUFFIX in (c.get("domain") or "")
                ]
                if any(c.get("name") == "cf_clearance" for c in cookies):
                    break
                time.sleep(1)

            if not any(c.get("name") == "cf_clearance" for c in cookies):
                raise ClearanceError(
                    "Cloudflare no entrego cf_clearance en "
                    f"{CHALLENGE_TIMEOUT_SEGUNDOS}s (titulo: {page.title()!r}). "
                    "Suele pasar si la IP esta temporalmente marcada: proba abrir "
                    "jkanime en Chrome a mano y reintentar"
                )

            user_agent = _read_user_agent(page)
            ahora = time.time()
            expira_cookie = next(
                (float(c["expires"]) for c in cookies
                 if c.get("name") == "cf_clearance" and float(c.get("expires") or 0) > 0),
                0.0,
            )
            expira = min(
                expira_cookie if expira_cookie > 0 else ahora + MAX_FRESH_SEGUNDOS,
                ahora + MAX_FRESH_SEGUNDOS,
            )
            return Clearance(
                cookies=cookies,
                user_agent=user_agent,
                obtained_at=ahora,
                expires_at=expira,
            )
        finally:
            browser.close()


def _read_user_agent(page) -> str:
    """Lee `navigator.userAgent` tolerando la navegacion del challenge.

    Cuando el challenge se resuelve, Cloudflare recarga la pagina y el contexto
    de ejecucion se destruye justo mientras se lee; de ahi el reintento.
    """
    for _ in range(20):
        try:
            return page.evaluate("navigator.userAgent")
        except Exception:
            time.sleep(0.5)
    raise ClearanceError("no se pudo leer navigator.userAgent de la pagina de jkanime")


def _load_state() -> Clearance | None:
    try:
        with STATE_FILE.open(encoding="utf-8") as fh:
            return Clearance.from_json(json.load(fh))
    except FileNotFoundError:
        return None
    except Exception as exc:
        logger.warning("Estado de cf_clearance ilegible (%s), se ignora", exc)
        return None


def _save_state(clearance: Clearance) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        temporal = STATE_FILE.with_suffix(".tmp")
        with temporal.open("w", encoding="utf-8") as fh:
            json.dump(clearance.to_json(), fh)
        temporal.replace(STATE_FILE)
    except Exception as exc:
        # No es fatal: la cookie vive en memoria igual.
        logger.warning("No se pudo guardar el estado de cf_clearance: %s", exc)
