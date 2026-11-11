"""Partidas seguidas: la media excluye la que está en curso e incluye la anterior en cuanto empieza otra."""
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import contador  # noqa: E402

tmp = Path(tempfile.mkdtemp())
contador.DATOS = tmp
(tmp / "antes.json").write_text(json.dumps({"partidas_antes": 90, "cofres_estimados": 3000}), encoding="utf-8")
with open(tmp / "cofres.jsonl", "w", encoding="utf-8") as f:
    n = 0
    for p, cuantos in (("A", 40), ("B", 30), ("C", 50), ("D", 40)):
        for _ in range(cuantos):
            n += 1
            f.write(json.dumps({"n": n, "fecha": "2026-11-02T20:00:00", "tipo": "COFRE", "partida": p}) + "\n")
contador.partida_actual = lambda: ("D", True, time.time() - 3000)
c = contador.Contador(lambda e: None)
bien = []


def revisar(nombre, cond, detalle):
    bien.append(bool(cond))
    print(("OK   " if cond else "MAL  ") + nombre, "" if cond else detalle)


revisar("en el lobby: 94 partidas, media 40, antes 3600", (c._partidas(), c._media(), c.antes) == (94, 40.0, 3600), (c._partidas(), c._media(), c.antes))

ahora = time.time()
c.partida = ("E", False, ahora)
c.antes = c._base_antes()
zona = np.zeros((10, 10, 4), np.uint8)
for _ in range(3):
    c.contar_cofre("COFRE", zona, 1.0)
fila = json.loads((tmp / "cofres.jsonl").read_text(encoding="utf-8").splitlines()[-1])
revisar("partida E en curso: sus cofres llevan «E» y no mueven la media", fila["partida"] == "E" and c._media() == 40.0 and c._partidas() == 95, (fila, c._media(), c._partidas()))

c.partida = ("F", False, ahora + 60)  # empieza otra sin esperar: E ya cuenta
c.antes = c._base_antes()
esperada = (40 + 30 + 50 + 40 + 3) / 5
revisar("partida F seguida: E entra a la media al instante", c._media() == esperada and c._partidas() == 96 and c.antes == round(90 * esperada), (c._media(), c._partidas(), c.antes))
c.contar_cofre("COFRE", zona, 2.0)
fila = json.loads((tmp / "cofres.jsonl").read_text(encoding="utf-8").splitlines()[-1])
revisar("el cofre de F lleva «F»", fila["partida"] == "F", fila)

c.partida = ("F", False, time.time() - 5000)  # repetición vieja: Fortnite no está grabando
c.contar_cofre("COFRE", zona, 3.0)
fila = json.loads((tmp / "cofres.jsonl").read_text(encoding="utf-8").splitlines()[-1])
revisar("sin repeticiones nuevas: el cofre queda sin partida", "partida" not in fila, fila)
print(f"{sum(bien)}/{len(bien)} bien")
shutil.rmtree(tmp, ignore_errors=True)
