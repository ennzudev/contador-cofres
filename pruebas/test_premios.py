"""Premios: de quién son, los letreros repetidos del OCR y el token pirata (texto de un ejemplo real)."""
import asyncio
import json
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import contador  # noqa: E402

FRAME = np.zeros((1440, 2560, 4), np.uint8)
ZONA = np.zeros((10, 10, 4), np.uint8)
bien = []


def nuevo():
    tmp = Path(tempfile.mkdtemp())
    contador.DATOS = tmp
    contador.DIAGNOSTICO = False
    contador.winsound.Beep = lambda *a: None
    return contador.Contador(lambda e: None), tmp


def leer_con(lineas):
    async def leer(_):
        return lineas
    return leer


def premios(tmp):
    f = tmp / "premios.jsonl"
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()] if f.exists() else []


def revisar(nombre, condicion, detalle):
    condicion = bool(condicion)
    bien.append(condicion)
    print(("OK   " if condicion else "MAL  ") + nombre, "" if condicion else detalle)


async def letrero(c, t, lineas):
    await c._leer_letrero(FRAME, leer_con(lineas), t)


async def avanzar(c, t):  # lo que hace procesar() con el premio pendiente, sin leer pantalla
    if c.premio_pendiente and t - c.premio_pendiente[1] > contador.VENTANA_PREMIO:
        p, _ = c.premio_pendiente
        c.premio_pendiente = None
        c._registrar_premio(p, None, t)


async def main():
    # 1. Variaciones del OCR del mismo letrero: un solo premio, y es tuyo (cofre 1 s antes).
    c, tmp = nuevo()
    c.contar_cofre("COFRE", ZONA, 9.0)
    for t, l in [(10, ["ENCONTRASTE", "ARTILVGIO DE", "ESPIRITU"]), (10.6, ["ENCONTRASTE", "ARTILVGIO DE", "ESPIRITU -4"]),
                 (11.2, ["ENCONTRASTE", "ARTILQGIO DE", "ESPIRITUS"])]:
        await letrero(c, t, l)
    p = premios(tmp)
    revisar("letrero repetido por el OCR: 1 premio, tuyo, cofre #1", len(p) == 1 and p[0]["cofre"] == 1 and p[0]["de"] == "tuyo", p)
    shutil.rmtree(tmp, ignore_errors=True)

    # 2. El letrero sale antes de que se confirme el cofre: espera y se liga al cofre.
    c, tmp = nuevo()
    await letrero(c, 20, ["ENCONTRASTE", "ARTILUGIO DE", "ESPIRITU"])
    c.contar_cofre("COFRE", ZONA, 21.2)
    p = premios(tmp)
    revisar("letrero antes que el cofre: se liga al cofre que llega 1.2 s después", len(p) == 1 and p[0]["cofre"] == 1, p)
    shutil.rmtree(tmp, ignore_errors=True)

    # 3. Sin cofre tuyo en VENTANA_PREMIO: de un compañero, y suma a tus premios.
    c, tmp = nuevo()
    await letrero(c, 30, ["ENCONTRASTE", "ARTILUGIO DE", "ESPIRITU"])
    await avanzar(c, 30 + contador.VENTANA_PREMIO + 0.5)
    p = premios(tmp)
    revisar("sin cofre tuyo: de un compañero, y sí suma a tus artilugios", len(p) == 1 and p[0]["cofre"] is None and p[0]["de"] != "tuyo" and c.premios, (p, c.premios))
    shutil.rmtree(tmp, ignore_errors=True)

    # 4. El token, con el texto del ejemplo real: «HAS ENCONTRADO / ACCESO A LA TIENDA / PIRATA».
    c, tmp = nuevo()
    c.contar_cofre("COFRE", ZONA, 39.5)
    await letrero(c, 40, ["A LA TIENDA", "HAS ENCONTRADO", "ACCESO A LA TIENDA", "PIRATA"])
    p = premios(tmp)
    capturas = list((tmp / "premios").glob("token-*.png"))
    revisar("token con «HAS ENCONTRADO»: tuyo, con captura completa y CONSEGUIDO",
            len(p) == 1 and p[0].get("token_pirata") and p[0]["premio"] == "ACCESO A LA TIENDA PIRATA" and capturas and c.token, (p, capturas))
    shutil.rmtree(tmp, ignore_errors=True)

    # 5. El token aunque el OCR no lea el encabezado.
    c, tmp = nuevo()
    await letrero(c, 50, ["ACCESO A LA TIENDA", "PIRATA"])
    revisar("token sin encabezado: la alerta sale al instante", c.premio is not None and c.premio["pirata"] and c.token, c.premio)
    await avanzar(c, 50 + contador.VENTANA_PREMIO + 0.5)
    p = premios(tmp)
    revisar("token sin cofre tuyo: queda como de un compañero (igual te da el acceso)", len(p) == 1 and p[0]["de"] != "tuyo" and p[0].get("token_pirata"), p)
    shutil.rmtree(tmp, ignore_errors=True)

    # 6. Una misión o un nombre de lugar no es un premio.
    c, tmp = nuevo()
    await letrero(c, 60, ["PUERTO PIRATA"])
    revisar("«PUERTO PIRATA» sin letrero: no es premio", not premios(tmp) and c.premio is None, premios(tmp))
    shutil.rmtree(tmp, ignore_errors=True)


asyncio.run(main())


# 7. El mismo letrero leído 4 veces en 6 s con texto ajeno pegado.
async def caso_texto_ajeno():
    c, tmp = nuevo()
    c.contar_cofre("COFRE", ZONA, 99.0)
    for t, l in [(100.0, ["ENCONTRASTE", "ARTILQGIO DE", "ESPIRITU p"]),
                 (100.9, ["ENCONTRASTE", "ARTILUGIO DE", "ESPIRITU", "ESCODFTn DF col"]),
                 (101.7, ["ENCONTRASTE", "ARTILVGIO DE", "ESPIRITU", "Espacio PARA PASA"]),
                 (105.8, ["ENCONTRASTE", "ARTILQGIÕ DE", "ESPIRITU", "BUSCAR", "No,puedes hacer"])]:
        await letrero(c, t, l)
    p = premios(tmp)
    revisar("texto ajeno: un solo premio, «ARTILQGIO DE ESPIRITU», del cofre #1", len(p) == 1 and p[0]["premio"] == "ARTILQGIO DE ESPIRITU" and p[0]["cofre"] == 1, p)
    shutil.rmtree(tmp, ignore_errors=True)
    # Y el token sigue completo con sus dos líneas.
    c, tmp = nuevo()
    await letrero(c, 200, ["HAS ENCONTRADO", "ACCESO A LA TIENDA", "PIRATA", "BUSCAR"])
    revisar("token: «ACCESO A LA TIENDA PIRATA» sin el BUSCAR", c.premio and c.premio["nombre"] == "ACCESO A LA TIENDA PIRATA", c.premio)
    shutil.rmtree(tmp, ignore_errors=True)


asyncio.run(caso_texto_ajeno())


# 8. Lecturas a medias del mismo letrero, y un cosmético que el letrero nombra distinto que la tienda.
async def caso_lecturas_a_medias():
    # El OCR se come «ARTILUGIO» 4 s después: sigue siendo el mismo premio, no uno de un compañero.
    c, tmp = nuevo()
    c.contar_cofre("COFRE", ZONA, 299.5)
    await letrero(c, 300, ["ENCONTRASTE", "ARTILVGIO DE", "ESPIRITU"])
    await letrero(c, 303.8, ["ENCONTRASTE", "DE ESPIRITU"])
    await avanzar(c, 312)
    p = premios(tmp)
    revisar("«DE ESPIRITU» después del artilugio: el mismo premio", len(p) == 1 and p[0]["de"] == "tuyo", p)
    shutil.rmtree(tmp, ignore_errors=True)
    # El Cadillac sale como «CALCOMANÍA DORADA PARA AUTO», 3.2 s después de su cofre, y 6 s después se
    # lee pegado al aviso de la tormenta.
    c, tmp = nuevo()
    c.semana = json.loads((Path(contador.__file__).parent / "ejemplos" / "semana.json").read_text(encoding="utf-8"))
    c.contar_cofre("COFRE", ZONA, 400.0)
    await letrero(c, 403.2, ["ENCONTRASTE", "CALCOMANíA DORADA", "-PARA AUTO"])
    await letrero(c, 409.0, ["ENCONTRASTE", "DORADA", "NUEVA FASE DE L"])
    await avanzar(c, 420)
    p = premios(tmp)
    revisar("calcomanía del Cadillac: un premio, tuyo, y marca el Cadillac",
            len(p) == 1 and p[0].get("cosmetico") == "cadillac-blackwing" and p[0]["de"] == "tuyo" and "cadillac-blackwing" in c.cosmeticos, p)
    shutil.rmtree(tmp, ignore_errors=True)
    # Una lectura a medias del token no esconde la buena que llega después.
    c, tmp = nuevo()
    await letrero(c, 500, ["HAS ENCONTRADO", "ACCESO A LA"])
    await letrero(c, 500.6, ["HAS ENCONTRADO", "ACCESO A LA TIENDA", "PIRATA"])
    revisar("token después de una lectura a medias: sale la alerta", c.token and c.premio and c.premio["pirata"], c.premio)
    shutil.rmtree(tmp, ignore_errors=True)


asyncio.run(caso_lecturas_a_medias())
print(f"{sum(bien)}/{len(bien)} bien en total")
