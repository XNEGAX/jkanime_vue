"""Localizacion del binario de ffmpeg.

`shutil.which("ffmpeg")` no alcanza en Windows: el PATH del proceso Django se
hereda al arrancar `run.bat`, y una instalacion hecha despues (winget deja los
shims en `%LOCALAPPDATA%\\Microsoft\\WinGet\\Links`) no aparece hasta reiniciar
la sesion. Buscar tambien en las ubicaciones conocidas evita fallar con ffmpeg
ya instalado, que es justo lo que producia descargas sin audio.
"""

import glob
import os
import shutil
from pathlib import Path

_FFMPEG = None
_FFMPEG_PROBED = False


def _candidates():
    """Rutas candidatas, en orden de preferencia."""
    env = os.environ.get("FFMPEG_PATH")
    if env:
        yield env

    which = shutil.which("ffmpeg")
    if which:
        yield which

    local = os.environ.get("LOCALAPPDATA")
    if local:
        yield os.path.join(local, "Microsoft", "WinGet", "Links", "ffmpeg.exe")
        pattern = os.path.join(
            local, "Microsoft", "WinGet", "Packages",
            "Gyan.FFmpeg*", "**", "bin", "ffmpeg.exe",
        )
        for match in sorted(glob.glob(pattern, recursive=True), reverse=True):
            yield match

    # Copia portable dentro del proyecto (backend/bin/ffmpeg/ffmpeg.exe).
    yield str(Path(__file__).resolve().parent.parent / "bin" / "ffmpeg" / "ffmpeg.exe")


def find_ffmpeg(force: bool = False) -> str | None:
    """Devuelve la ruta absoluta a ffmpeg, o None si no esta instalado.

    El resultado se cachea por proceso. `force=True` vuelve a probar, para el
    caso de una instalacion hecha con la app ya corriendo.
    """
    global _FFMPEG, _FFMPEG_PROBED

    if _FFMPEG_PROBED and not force:
        return _FFMPEG

    for candidate in _candidates():
        if candidate and os.path.isfile(candidate):
            _FFMPEG = candidate
            _FFMPEG_PROBED = True
            return _FFMPEG

    _FFMPEG = None
    _FFMPEG_PROBED = True
    return None
