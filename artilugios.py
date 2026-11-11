"""Reconoce qué artilugio salió por el ícono del letrero «ENCONTRASTE / ARTILUGIO DE ESPÍRITU».

El texto del letrero es el mismo para los cinco artilugios; lo que cambia es el ícono, que va sobre una
tarjeta dorada. Se comparan los colores del ícono que no son dorados contra los de cada ícono de `assets/`.
"""

from pathlib import Path

import numpy as np
from PIL import Image

from config import CONFIG

ASSETS = Path(__file__).parent / "assets"
ARTILUGIOS = {
    "acelerador-de-extraccion": "Acelerador de extracción",
    "extractor-portatil": "Extractor portátil",
    "localizador-de-suerte": "Localizador de suerte",
    "localizador-de-espiritus": "Localizador de espíritus",
    "fuego-artificial-dorado": "Fuego artificial dorado",
}
# La tarjeta del ícono en una pantalla de 2560x1440 (x0, y0, x1, y1); `config.json` la corrige («zonas» › «icono»).
ZONA_ICONO = tuple(CONFIG["zonas"].get("icono", (1195, 170, 1375, 335)))


def rasgos(rgb: np.ndarray, alfa: np.ndarray | None = None) -> np.ndarray:
    """Qué parte del ícono es verde, roja, morada, azul u oscura, y cuánto no es dorado."""
    img = Image.fromarray(rgb.astype(np.uint8)).convert("HSV")
    h, s, v = (np.asarray(img)[..., i].astype(float) for i in range(3))
    h, s, v = h * 360 / 255, s / 255, v / 255
    visible = np.ones_like(h, bool) if alfa is None else alfa > 128
    dorado = (h >= 20) & (h <= 60) & (s > 0.35) & (v > 0.45)
    pieza = visible & ~dorado
    n = max(pieza.sum(), 1)
    color = s > 0.35
    clases = [
        (h >= 70) & (h <= 160) & color & (v > 0.15),  # verde
        ((h < 15) | (h > 340)) & color & (v > 0.3),  # rojo
        (h >= 260) & (h <= 335) & color & (v > 0.2),  # morado
        (h >= 190) & (h < 260) & color & (v > 0.15),  # azul
        v < 0.2,  # oscuro
    ]
    fracciones = [(c & pieza).sum() / n for c in clases]
    return np.array(fracciones + [pieza.sum() / max(visible.sum(), 1)])


_referencias: dict[str, np.ndarray] | None = None


def _refs() -> dict[str, np.ndarray]:
    global _referencias
    if _referencias is None:
        _referencias = {}
        for clave in ARTILUGIOS:
            img = np.asarray(Image.open(ASSETS / f"{clave}.png").convert("RGBA"))
            _referencias[clave] = rasgos(img[..., :3], img[..., 3])
    return _referencias


def reconocer(rgb_pantalla: np.ndarray) -> tuple[str | None, float]:
    """Dado el recorte RGB de ZONA_ICONO, la clave del artilugio más parecido (None si ninguno se
    parece) y su distancia. Solo cuentan los cinco colores: cuánto no es dorado depende de la tarjeta,
    que en pantalla rodea al ícono y en el asset no está."""
    r = rasgos(rgb_pantalla)[:5]
    distancias = {k: float(np.abs(r - ref[:5]).sum()) for k, ref in _refs().items()}
    mejor = min(distancias, key=distancias.get)
    return (mejor if distancias[mejor] < 0.6 else None), distancias[mejor]
