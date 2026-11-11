"""Quita el fondo blanco de los íconos de `assets/originales/` y los deja recortados en `assets/`.

Se corre una vez, o cuando se agregue un ícono nuevo: `python preparar_assets.py [nombre ...]`. Sin
nombres, prepara los de ICONOS que tengan su original.
"""

import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

AQUI = Path(__file__).parent / "assets"
ICONOS = [
    "token-pirata",
    "cofre",
    "extractor-portatil",
    "acelerador-de-extraccion",
    "localizador-de-suerte",
    "localizador-de-espiritus",
    "fuego-artificial-dorado",
    # Cosméticos de la semana 2, de fortnite-api.com (ya traen fondo transparente).
    "traje-lil-uzi-dorado",
    "mochila-diamante-y-oro",
    "cadillac-blackwing",
]
LADO = 160  # px del lado mayor del ícono ya recortado


def sin_fondo(img: Image.Image) -> Image.Image:
    """Transparenta el blanco que toca el borde (relleno desde las orillas), no el blanco de adentro."""
    rgb = np.asarray(img.convert("RGB")).astype(np.int16)
    blanco = (rgb.min(axis=2) > 225) & ((rgb.max(axis=2) - rgb.min(axis=2)) < 25)
    h, w = blanco.shape
    fondo = np.zeros_like(blanco)
    cola = deque((y, x) for y in range(h) for x in (0, w - 1)) + deque((y, x) for x in range(w) for y in (0, h - 1))
    while cola:
        y, x = cola.popleft()
        if fondo[y, x] or not blanco[y, x]:
            continue
        fondo[y, x] = True
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not fondo[ny, nx] and blanco[ny, nx]:
                cola.append((ny, nx))
    alfa = Image.fromarray(np.where(fondo, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))
    salida = img.convert("RGBA")
    salida.putalpha(alfa)
    return salida.crop(salida.getbbox())


for nombre in sys.argv[1:] or ICONOS:
    origen = AQUI / "originales" / f"{nombre}.png"
    if not origen.exists():
        print(nombre, "sin original en assets/originales/")
        continue
    img = Image.open(origen)
    if max(img.size) > 600:  # los grandes se reducen antes del relleno, que es lento
        img.thumbnail((600, 600), Image.LANCZOS)
    if img.mode == "RGBA" and img.getextrema()[3][0] < 255:  # ya trae transparencia: solo se recorta
        icono = img.crop(img.getbbox())
    else:
        icono = sin_fondo(img)
    icono.thumbnail((LADO, LADO), Image.LANCZOS)
    icono.save(AQUI / f"{nombre}.png")
    print(nombre, icono.size)
