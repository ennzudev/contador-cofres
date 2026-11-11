"""Conteo de cofres con un OCR falso: cada zona devuelve las líneas que el caso diga."""
import asyncio
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import contador  # noqa: E402

FRAME = np.zeros((1440, 2560, 4), np.uint8)
ANCHO = {k: x1 - x0 for k, (x0, _, x1, _) in contador.ZONAS.items()}  # cada zona se reconoce por su ancho
R, C, S = "COFRE RARO", "COFRE", "COFRE DE ESPÍRITUS"


def caso(nombre, pasos, esperado_tipos):
    """pasos: lista de (segundos, líneas del aviso, valor de la misión o None). Las líneas del aviso pueden
    ser un par (lectura tal cual, lectura realzada) cuando las dos leen distinto."""
    tmp = Path(tempfile.mkdtemp())
    contador.DATOS = tmp
    contador.DIAGNOSTICO = False
    c = contador.Contador(lambda e: None)
    estado = {"xp": [], "mision": []}

    async def leer(zona):
        w = zona.shape[1]
        if w in (ANCHO["xp"], 2 * ANCHO["xp"]):  # el aviso, tal cual y realzado al doble
            xp = estado["xp"]
            return xp[w != ANCHO["xp"]] if isinstance(xp, tuple) else xp
        if w == ANCHO["mision"]:
            return estado["mision"]
        return []

    async def correr():
        t = 0.0
        for dur, xp, mision in pasos:
            estado["xp"] = xp
            estado["mision"] = [f"{mision}/100 Abre cofres de espíritus"] if mision is not None else []
            fin = t + dur
            while t < fin:
                await c.procesar(FRAME, leer, ahora=t)
                t += 0.3

    asyncio.run(correr())
    filas = [l for l in (tmp / "cofres.jsonl").read_text(encoding="utf-8").splitlines()] if (tmp / "cofres.jsonl").exists() else []
    import json

    tipos = [(json.loads(f)["tipo"], json.loads(f).get("fuente", "aviso")) for f in filas]
    ok = tipos == esperado_tipos
    print(("OK  " if ok else "MAL ") + nombre, tipos if not ok else "")
    shutil.rmtree(tmp, ignore_errors=True)
    return ok


resultados = [
    caso("un cofre normal", [(1, [], 90), (2, ["+600 PE", C], 90), (1, [], 90)], [("COFRE", "aviso")]),
    caso(
        "bóveda apilada R, C, R, S",
        [(1, [], 90), (1.5, ["+900 PE", R], 90), (1.5, ["+1500 PE", R, C], 90), (1.5, ["+2400 PE", R, C, R], 90),
         (2, ["+3300 PE", R, C, R, S], 91), (1, [], 91)],
        [("COFRE RARO", "aviso"), ("COFRE", "aviso"), ("COFRE RARO", "aviso"), ("COFRE DE ESPIRITUS", "aviso")],
    ),
    caso(
        "aviso nuevo sin hueco: raro y luego espíritu",
        [(1, [], 90), (2, ["+900 PE", R], 90), (2, ["+900 PE", S], 91), (1, [], 91)],
        [("COFRE RARO", "aviso"), ("COFRE DE ESPIRITUS", "aviso")],
    ),
    caso(
        "la misión sube y el aviso no trae el espíritu: lo cuenta la misión",
        [(1, [], 90), (2, ["+900 PE", R], 90), (5, ["+900 PE", R], 91), (1, [], 91)],
        [("COFRE RARO", "aviso"), ("COFRE DE ESPIRITUS", "misión")],
    ),
    caso(
        "la misión sube antes que el aviso: no cuenta doble",
        [(1, [], 90), (0.7, [], 91), (2, ["+900 PE", S], 91), (5, [], 91)],
        [("COFRE DE ESPIRITUS", "aviso")],
    ),
    caso(
        "aviso largo que pierde su primera línea al crecer",
        [(1, [], 90), (1.5, ["PE", R], 90), (1.5, ["PE", R, C], 90), (1.5, ["PE", R, C, R], 90),
         (1.5, ["PE", R, C, R, C], 90), (1.5, ["PE", R, C, R, C, R], 90), (1.5, ["PE", C, R, C, R, C], 90), (1, [], 90)],
        [("COFRE RARO", "aviso"), ("COFRE", "aviso"), ("COFRE RARO", "aviso"), ("COFRE", "aviso"),
         ("COFRE RARO", "aviso"), ("COFRE", "aviso")],
    ),
    caso("caja de munición: no cuenta", [(1, [], 90), (2, ["+300 PE", "CAJA DE MUNICIÓN"], 90), (1, [], 90)], []),
    caso("misión de cofres en pantalla: no cuenta", [(1, [], 90), (2, ["Abre cofres de espíritus"], 90)], []),
    # Fortnite junta los cofres iguales: «COFRE RARO X3». Lecturas reales del OCR de una bóveda, con
    # 4 raros y 1 de espíritus; el cuarto raro llega en un aviso nuevo pegado al anterior.
    caso(
        "bóveda con «X2», «X3» y un aviso nuevo pegado",
        [(1, [], 94), (1.5, ["+900 PE", R], 94), (1.5, (["+1800 PE", "COFRE RARO 12"], ["+1800 PE", "COFRE RARO '(2"]), 94),
         (1.5, (["+2950 PE", "COFRE RARO 13", "MUNICIÓN MÁXIMA"], ["+2950 PE", R, "MUNICIÓN MÁXIMA"]), 94),
         (2, ["+3850 PE", "COFRE RARO 13", "MUNICIÓN MÁXIMA", S], 95), (2, ["+900 PE", R], 95), (1, [], 95)],
        [("COFRE RARO", "aviso")] * 3 + [("COFRE DE ESPIRITUS", "aviso"), ("COFRE RARO", "aviso")],
    ),
    caso(
        "dos cofres normales en el mismo aviso: «COFRE X2», también pegado",
        [(1, [], 90), (1.5, ["+600 PE", C], 90), (1.5, (["+1200 PE", "COFRE 12"], ["+1200 PE", "*coFREX2"]), 90), (1, [], 90)],
        [("COFRE", "aviso"), ("COFRE", "aviso")],
    ),
    caso("un número suelto no multiplica: «COFRE 9»", [(1, [], 90), (2, ["+600 PE", "COFRE 9"], 90), (1, [], 90)], [("COFRE", "aviso")]),
    caso(
        "aviso nuevo pegado con el mismo cofre: lo dicen los PE",
        [(1, [], 90), (1.5, ["+850 PE", C, "MUNICIÓN MÁXIMA"], 90), (1.5, ["+600 PE", C], 90), (1, [], 90)],
        [("COFRE", "aviso"), ("COFRE", "aviso")],
    ),
    caso(
        "unos PE mal leídos una sola vez no son un aviso nuevo",
        [(1, [], 90), (1.5, ["+850 PE", C, "MUNICIÓN MÁXIMA"], 90), (0.3, ["+600 PE", C, "MUNICIÓN MÁXIMA"], 90),
         (1.5, ["+850 PE", C, "MUNICIÓN MÁXIMA"], 90), (1, [], 90)],
        [("COFRE", "aviso")],
    ),
]
print(f"{sum(resultados)}/{len(resultados)} casos bien")
