"""Dibuja el recuadro del contador con el estilo de Caza del tesoro: un PNG por estado.

`dibujar(estado, ahora)` devuelve una imagen RGB; lo que queda fuera del panel redondeado es del color
`TRANSPARENTE`, que la ventana vuelve invisible.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ASSETS = Path(__file__).parent / "assets"
FUENTE = r"C:\Windows\Fonts\bahnschrift.ttf"
TRANSPARENTE = (1, 2, 3)

ANCHO = 430
DORADO = (247, 207, 96)
DORADO_OSCURO = (176, 128, 40)
BLANCO = (255, 255, 255)
GRIS = (170, 176, 200)
COLOR_TIPO = {
    "COFRE": (240, 182, 58),
    "COFRE RARO": (64, 160, 255),
    "COFRE DE ESPIRITUS": (186, 96, 255),
    "COFRE ROTO": (255, 110, 70),
}
NOMBRE_TIPO = {"COFRE": "NORMAL", "COFRE RARO": "RARO", "COFRE DE ESPIRITUS": "ESPÍRITU", "COFRE ROTO": "ROTO"}

# Probabilidad por cofre, de una tabla de terceros de la semana 2 (Lil Uzi); Epic no la publica.
PROB_TOKEN = 1 / 137_500

ARTILUGIOS = {
    "acelerador-de-extraccion": "Acelerador de extracción",
    "extractor-portatil": "Extractor portátil",
    "localizador-de-suerte": "Localizador de suerte",
    "localizador-de-espiritus": "Localizador de espíritus",
    "fuego-artificial-dorado": "Fuego artificial dorado",
}

DURA_RECIEN = 1.5  # s que brilla el número tras contar un cofre
DURA_PREMIO = 12  # s que se muestra la franja del premio


def _fuente(tam: int, variante: str = "Bold Condensed") -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(FUENTE, tam)
    f.set_variation_by_name(variante)
    return f


_iconos: dict[str, Image.Image] = {}


def icono(nombre: str, lado: int) -> Image.Image:
    clave = f"{nombre}@{lado}"
    if clave not in _iconos:
        ruta = ASSETS / f"{nombre}.png"
        if not ruta.exists():  # un cosmético de la semana sin ícono todavía: el cofre en su lugar
            ruta = ASSETS / "cofre.png"
        img = Image.open(ruta).convert("RGBA")
        img.thumbnail((lado, lado), Image.LANCZOS)
        _iconos[clave] = img
    return _iconos[clave]


def prob_token(cofres: int) -> float:
    return 1 - (1 - PROB_TOKEN) ** cofres


def _brillo(capa: Image.Image, color: tuple, radio: int) -> Image.Image:
    """Un halo del color dado alrededor de lo opaco de `capa`."""
    alfa = capa.split()[-1].filter(ImageFilter.GaussianBlur(radio))
    halo = Image.new("RGBA", capa.size, color + (0,))
    halo.putalpha(alfa.point(lambda a: min(255, a * 2)))
    return halo


def _texto(d: ImageDraw.ImageDraw, xy, texto, fuente, color, sombra=True, anchor="la"):
    if sombra:
        d.text((xy[0] + 2, xy[1] + 2), texto, font=fuente, fill=(0, 0, 0, 160), anchor=anchor)
    d.text(xy, texto, font=fuente, fill=color, anchor=anchor)


def _miles(n: int) -> str:
    return f"{n:,}"


def dibujar(e: dict, ahora: float) -> Image.Image:
    """`e`: total, antes, sesion, tipo, fuente_tipo, recien, premio (o None), premios (clave -> cuántos)."""
    alerta = bool(e.get("premio") and e["premio"].get("pirata"))
    premio = e.get("premio") if e.get("premio") and (alerta or ahora - e["premio"]["cuando"] < DURA_PREMIO) else None
    BASE = 224
    # Abajo va la franja del premio mientras dura; si no, lo que falta de la semana. Nunca las dos, para
    # que el recuadro no crezca hasta los avisos de eliminaciones.
    semana = None if premio else e.get("semana")
    alto = BASE + (64 if premio else 66 if semana else 0)
    lienzo = Image.new("RGBA", (ANCHO, alto), (0, 0, 0, 0))

    # Panel: degradado de noche pirata con marco dorado; dorado entero si salió el token.
    fondo = Image.new("RGBA", (ANCHO, alto))
    arriba, abajo = ((70, 46, 8), (130, 90, 20)) if alerta else ((16, 22, 50), (34, 18, 64))
    for y in range(alto):
        t = y / max(alto - 1, 1)
        fondo.paste(tuple(int(a + (b - a) * t) for a, b in zip(arriba, abajo)) + (255,), (0, y, ANCHO, y + 1))
    mascara = Image.new("L", (ANCHO, alto), 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, ANCHO - 1, alto - 1), radius=16, fill=255)
    lienzo.paste(fondo, (0, 0), mascara)
    d = ImageDraw.Draw(lienzo)
    d.rounded_rectangle((1, 1, ANCHO - 2, alto - 2), radius=16, outline=DORADO, width=3)
    d.rounded_rectangle((6, 6, ANCHO - 7, alto - 7), radius=12, outline=DORADO_OSCURO + (140,), width=1)

    # Cofre a la izquierda.
    cofre = icono("token-pirata" if alerta else "cofre", 92)
    lienzo.alpha_composite(cofre, (18, 16 + (106 - cofre.height) // 2))

    # Número grande, con brillo un momento después de contar.
    x = 124
    _texto(d, (x, 16), "COFRES", _fuente(17, "SemiBold Condensed"), DORADO)
    # Un solo total: lo registrado más lo de antes del contador, sin separarlos como «aproximado».
    numero = _miles(e["total"] + e.get("antes", 0))
    f_num = _fuente(58)
    if e.get("recien") is not None and ahora - e["recien"] < DURA_RECIEN:
        capa = Image.new("RGBA", lienzo.size, (0, 0, 0, 0))
        ImageDraw.Draw(capa).text((x, 34), numero, font=f_num, fill=DORADO + (255,))
        lienzo.alpha_composite(_brillo(capa, DORADO, 8))
        d = ImageDraw.Draw(lienzo)
    _texto(d, (x, 34), numero, f_num, BLANCO)
    ancho_num = d.textlength(numero, font=f_num)
    _texto(d, (x + ancho_num + 10, 52), f"+{e['sesion']} hoy", _fuente(20, "SemiBold Condensed"), DORADO)

    # Tipo del último cofre, como etiqueta de color.
    if e.get("tipo"):
        etiqueta = "ÚLTIMO: " + NOMBRE_TIPO.get(e["tipo"], e["tipo"])
        if e.get("fuente_tipo") == "misión":
            etiqueta += " · por la misión"
        f_et = _fuente(15, "SemiBold Condensed")
        w = d.textlength(etiqueta, font=f_et) + 18
        color = COLOR_TIPO.get(e["tipo"], DORADO)
        d.rounded_rectangle((x, 100, x + w, 122), radius=11, fill=color + (60,), outline=color, width=2)
        d.text((x + 9, 111), etiqueta, font=f_et, fill=BLANCO, anchor="lm")

    # Arriba a la derecha, lo estimado de antes; abajo, una fila con los cinco artilugios encontrados
    # (siempre en el mismo orden, para que no salten de lugar) y la probabilidad del token.
    f_peq = _fuente(15, "SemiBold Condensed")
    total_con_antes = e["total"] + e.get("antes", 0)
    if e.get("partidas"):  # arriba a la derecha: cuántas partidas y cuánto abres en promedio
        texto = f"{e['partidas']} partidas"
        if e.get("media"):
            texto += f" · {e['media']:.1f} por partida"
        _texto(d, (ANCHO - 16, 18), texto, f_peq, GRIS, anchor="ra")
    d.line((18, 132, ANCHO - 18, 132), fill=DORADO_OSCURO + (160,), width=1)
    _texto(d, (18, 138), "ARTILUGIOS ENCONTRADOS", _fuente(13, "SemiBold Condensed"), GRIS, sombra=False)
    premios = e.get("premios", {})
    ancho_celda = (ANCHO - 36) / len(ARTILUGIOS)
    f_cant = _fuente(19)
    for i, clave in enumerate(ARTILUGIOS):
        cuantos = premios.get(clave, 0)
        cx = int(18 + i * ancho_celda)
        ic = icono(clave, 30)
        if not cuantos:  # sin ninguno: el ícono apagado
            ic = ic.copy()
            ic.putalpha(ic.split()[-1].point(lambda a: a // 3))
        lienzo.alpha_composite(ic, (cx, 154 + (30 - ic.height) // 2))
        _texto(d, (cx + ic.width + 4, 170), f"×{cuantos}", f_cant, BLANCO if cuantos else GRIS, anchor="lm")
    tok = icono("token-pirata", 22)
    if e.get("token"):  # sale una vez por cuenta: ya no hay probabilidad que mostrar
        texto_tok = "Token pirata · ¡CONSEGUIDO!"
    else:
        texto_tok = f"Token pirata · {prob_token(total_con_antes) * 100:.1f} % de probabilidad acumulada"
    w = d.textlength(texto_tok, font=f_peq)
    lienzo.alpha_composite(tok, (int(ANCHO - 16 - w - 26), 208 - 22 + 4))
    _texto(d, (ANCHO - 16, 208), texto_tok, f_peq, DORADO, anchor="rs")

    # Franja del premio recién salido.
    if premio:
        y0 = BASE
        color = DORADO if alerta else (186, 96, 255)
        d.rounded_rectangle((12, y0 - 4, ANCHO - 13, y0 + 52), radius=12, fill=color + (55,), outline=color, width=2)
        clave = premio.get("artilugio") or premio.get("cosmetico")
        ic = icono("token-pirata" if alerta else (clave or "cofre"), 46)
        capa = Image.new("RGBA", lienzo.size, (0, 0, 0, 0))
        capa.alpha_composite(ic, (22, y0 + 24 - ic.height // 2))
        lienzo.alpha_composite(_brillo(capa, color, 6))
        lienzo.alpha_composite(capa)
        d = ImageDraw.Draw(lienzo)
        titulo = "¡TOKEN PIRATA!" if alerta else (ARTILUGIOS.get(clave) or premio["nombre"].title())
        _texto(d, (78, y0 + 2), titulo.upper(), _fuente(24), BLANCO)
        if premio.get("cofre"):
            sub = f"Salió del cofre #{_miles(premio['cofre'])}"
        else:
            sub = "Sin cofre tuyo: de un compañero o de un cofre roto"
        _texto(d, (78, y0 + 30), sub, _fuente(16, "SemiBold Condensed"), DORADO if premio.get("cofre") else GRIS)

    # Lo que falta de la semana: apagado hasta que sale, encendido con palomita cuando ya lo tienes.
    if semana:
        y0 = BASE
        d.line((18, y0 - 6, ANCHO - 18, y0 - 6), fill=DORADO_OSCURO + (160,), width=1)
        completa = all(it["tienes"] for it in semana["items"])
        titulo = semana["titulo"].replace("TE FALTA", "¡COMPLETA!") if completa else semana["titulo"]
        _texto(d, (18, y0), titulo, _fuente(13, "SemiBold Condensed"), DORADO if completa else GRIS, sombra=False)
        ancho_celda = (ANCHO - 36) / len(semana["items"])
        f_nom = _fuente(17, "SemiBold Condensed")
        for i, it in enumerate(semana["items"]):
            cx = int(18 + i * ancho_celda)
            ic = icono(it["clave"], 38)
            if not it["tienes"]:
                ic = ic.copy()
                ic.putalpha(ic.split()[-1].point(lambda a: a * 2 // 5))
            lienzo.alpha_composite(ic, (cx, y0 + 18 + (38 - ic.height) // 2))
            d = ImageDraw.Draw(lienzo)
            tx = cx + ic.width + 6
            if it["tienes"]:  # palomita dibujada: la fuente no trae el símbolo
                verde = (120, 230, 120)
                d.line([(tx, y0 + 37), (tx + 4, y0 + 42), (tx + 12, y0 + 31)], fill=verde, width=3)
                tx += 16
            _texto(d, (tx, y0 + 37), it["nombre"], f_nom, (120, 230, 120) if it["tienes"] else GRIS, anchor="lm")

    salida = Image.new("RGB", lienzo.size, TRANSPARENTE)
    salida.paste(lienzo, (0, 0), lienzo)
    return salida
