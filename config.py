"""Lo que cambia de una PC a otra vive en `config.json`, junto al programa, y no va al repo.

Lo que `config.json` no traiga se toma de `ejemplos/config.json`. Qué es cada clave: README.md.
"""

import json
from pathlib import Path

AQUI = Path(__file__).parent


def _leer(ruta: Path) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}


CONFIG: dict = {**_leer(AQUI / "ejemplos" / "config.json"), **_leer(AQUI / "config.json")}
