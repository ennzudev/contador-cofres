"""OCR con el motor integrado de Windows (Windows.Media.Ocr), en el idioma de `config.json` (es-MX de fábrica)."""

import numpy as np
from winrt.windows.globalization import Language
from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.storage.streams import DataWriter

from config import CONFIG

_engine = OcrEngine.try_create_from_language(Language(CONFIG["idioma_ocr"]))
if _engine is None:
    raise RuntimeError(f"Windows no tiene instalado el OCR en {CONFIG['idioma_ocr']}")


def _bitmap(bgra: np.ndarray) -> SoftwareBitmap:
    h, w = bgra.shape[:2]
    writer = DataWriter()
    writer.write_bytes(np.ascontiguousarray(bgra, dtype=np.uint8).tobytes())
    return SoftwareBitmap.create_copy_from_buffer(writer.detach_buffer(), BitmapPixelFormat.BGRA8, w, h)


async def leer(bgra: np.ndarray) -> list[str]:
    """Devuelve las líneas de texto que el OCR encuentra en una imagen BGRA."""
    resultado = await _engine.recognize_async(_bitmap(bgra))
    return [linea.text for linea in resultado.lines]
