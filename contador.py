"""Contador de cofres de Fortnite.

Solo mira la pantalla (como OBS): no lee la memoria del juego ni se mete en él.
Con el OCR de Windows lee tu aviso de experiencia, que trae una línea por cada cosa que abres
(«COFRE», «COFRE RARO», «COFRE DE ESPÍRITUS», «CAJA DE MUNICIÓN»...), y el letrero de premio
(«ENCONTRASTE ...»). Registra cada cofre y cada premio en `datos/`.

Arranca con Windows y espera: lee solo mientras Fortnite está abierto y al frente.
El recuadro deja pasar los clics; para cerrarlo, `detener.cmd`.
"""

import asyncio
import ctypes
import ctypes.wintypes
import json
import queue
import re
import threading
import time
import tkinter as tk
import unicodedata
import winsound
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from itertools import zip_longest
from pathlib import Path

import mss
import numpy as np
import psutil
from PIL import Image, ImageOps, ImageTk

import artilugios
import estilo
from config import CONFIG

DATOS = Path(__file__).parent / "datos"
# Cada partida deja su repetición aquí: su nombre identifica la partida de cada cofre.
DEMOS = Path.home() / "AppData" / "Local" / "FortniteGame" / "Saved" / "Demos"
FORTNITE = "FortniteClient-Win64-Shipping.exe"

# Zonas en coordenadas de una pantalla de 2560x1440: (x0, y0, x1, y1). Se escalan a otra resolución.
ZONAS = {
    # Tu aviso de experiencia: «+4350 PE» y debajo una línea por cosa, en el orden en que la abriste.
    # Crece hacia arriba y hacia abajo mientras sigas abriendo cosas.
    "xp": (1450, 200, 2300, 720),
    # El letrero de premio: «ENCONTRASTE / ARTILUGIO DE ESPÍRITU» sale arriba del centro; el del token,
    # «HAS ENCONTRADO / ACCESO A LA TIENDA PIRATA», más abajo (ejemplos de otros jugadores).
    "letrero": (760, 250, 1800, 900),
    "mision": (40, 40, 700, 260),  # «86/100 Abre cofres de espíritus», solo para comprobar
}
# Si en otra PC el juego acomoda distinto, `config.json` las corrige («zonas»).
ZONAS.update({k: tuple(v) for k, v in CONFIG["zonas"].items() if k in ZONAS})

PERIODO = 0.2  # segundos entre lecturas
# El aviso se lee unos 2 s y desaparece de golpe; a media vida el OCR se salta a lo mucho una lectura.
AVISO_CERRADO = 0.75  # segundos sin leer nada del aviso: se cerró, y el siguiente empieza de cero
MISION_COFRES = re.compile(r"(\d{1,3})\s*/\s*(\d{1,3})\s*ABRE COFRES DE ESP")
# Fortnite junta en una línea los cofres iguales del mismo aviso: «COFRE RARO X3» son tres. El OCR lee la
# «X» como «X», «1» o «(» («COFRE RARO 13», «COFRE RARO '(2»); un número suelto («COFRE 9») es basura.
MULTIPLICADOR = re.compile(r"(?:X|1|\()\s*([2-9])(?!\d)")
ESPIRITU = "COFRE DE ESPIRITUS"
ROTO = "COFRE ROTO"
# s entre tu cofre y su letrero de premio; fuera de eso es de un compañero. El letrero tarda en salir:
# el de la calcomanía del Cadillac llegó 3.2 s después de su cofre.
VENTANA_PREMIO = 5
# Para revisar lo que lee en una PC nueva: anota cada cambio del aviso de PE con su foto en
# `datos/diagnostico/` (se guardan las últimas DIAG_MAX).
DIAGNOSTICO = bool(CONFIG["diagnostico"])
DIAG_MAX = 1500


def tecla_virtual(nombre: str | int | None) -> int | None:
    """La tecla de `config.json`: «F1» a «F24», o un código de tecla virtual; None si no hay botón."""
    if nombre is None or isinstance(nombre, int):
        return nombre
    m = re.fullmatch(r"F(\d{1,2})", nombre.strip().upper())
    if not m or not 1 <= int(m.group(1)) <= 24:
        raise ValueError(f"tecla_roto no válida: {nombre!r}")
    return 0x6F + int(m.group(1))  # F1 es 0x70 y las siguientes van seguidas


# Al romper un cofre Fortnite no muestra nada en pantalla: se cuenta picando esta tecla. La que no existe
# en el teclado (F13 a F24, mapeada a un botón del mouse) no choca con Fortnite ni con el chat; una que sí
# existe deja de llegarle al juego mientras el contador corre.
TECLA_ROTO = tecla_virtual(CONFIG["tecla_roto"])


def norm(texto: str) -> str:
    """Mayúsculas, sin acentos y con espacios simples, para comparar lo que lee el OCR."""
    sin_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sin_acentos).upper().strip()


def tipo_de_cofre(linea: str) -> tuple[str, int] | None:
    """El tipo de cofre de una línea del aviso («COFRE», «COFRE RARO» o «COFRE DE ESPIRITUS») y cuántos
    trae («COFRE RARO X3» son tres); None si la línea no es de un cofre."""
    texto = norm(linea.replace("×", "X"))
    palabras = re.findall(r"[A-Z]{2,}", texto)
    # «COFRES» es una misión, no un cofre; «COFREX2» es un cofre con su «X2» pegada.
    if not palabras or not palabras[0].startswith("COFRE") or palabras[0].startswith("COFRES"):
        return None
    resto = " ".join(palabras)[len("COFRE") :]
    m = MULTIPLICADOR.search(texto, texto.find("COFRE") + len("COFRE"))
    cuantos = int(m.group(1)) if m else 1
    if "RARO" in resto:
        return "COFRE RARO", cuantos
    if "ESPIRIT" in resto:
        return ESPIRITU, cuantos
    return "COFRE", cuantos


def parecidos(a: str, b: str) -> bool:
    """Dos lecturas del mismo letrero: casi el mismo texto, una palabra larga en común («DORADA»), o una
    lectura a medias cuyas palabras caben todas en la otra («A DE» en «ARTILVGIO DE ESPIRITU»)."""
    largas = lambda t: set(re.findall(r"[A-Z]{5,}", t))  # noqa: E731
    dentro = lambda x, y: all(p in y for p in x.split())  # noqa: E731
    return SequenceMatcher(None, a, b).ratio() > 0.75 or bool(largas(a) & largas(b)) or dentro(a, b) or dentro(b, a)


def pe_del_aviso(lineas: list[str]) -> int | None:
    """Los PE que suma el aviso («+3850 PE»): crecen mientras el aviso sigue abierto."""
    pes = [int(m.group(1)) for l in lineas if (m := re.search(r"\+\s*(\d{2,5})\s*PE\b", norm(l)))]
    return max(pes) if pes else None


def partida_actual() -> tuple[str, bool, float] | None:
    """La repetición más nueva: su nombre, si la partida ya terminó y cuándo empezó.

    Terminó si la repetición lleva 2 min sin escribirse y se escribió después de crearse: si Fortnite la
    escribiera solo al final, a media partida tendría la hora de creación y no se daría por terminada.
    Al empezar otra partida, la anterior deja de ser la más nueva y cuenta como terminada de inmediato.
    """
    try:
        repeticiones = [(p.stat(), p) for p in DEMOS.glob("*.replay")]
    except OSError:
        return None
    if not repeticiones:
        return None
    st, p = max(repeticiones, key=lambda r: r[0].st_ctime)
    terminada = time.time() - st.st_mtime > 120 and st.st_mtime - st.st_ctime > 60
    return p.stem, terminada, st.st_ctime


def jornada(momento: datetime):
    """El día de juego: va de 6 a. m. a 6 a. m., para que una noche que pasa de medianoche sea un solo día."""
    return (momento - timedelta(hours=6)).date()


def recortar(frame: np.ndarray, zona: str | tuple) -> np.ndarray:
    """Una zona de ZONAS (o una caja propia) en coordenadas de 2560x1440, escalada a la pantalla."""
    escala = frame.shape[1] / 2560
    x0, y0, x1, y1 = (int(v * escala) for v in (ZONAS[zona] if isinstance(zona, str) else zona))
    return frame[y0:y1, x0:x1]


def realzar(bgra: np.ndarray) -> np.ndarray:
    """Gris, contraste estirado y al doble de tamaño: ayuda con el aviso semitransparente."""
    gris = ImageOps.autocontrast(Image.fromarray(bgra[..., 2::-1]).convert("L"), cutoff=2)
    gris = gris.resize((gris.width * 2, gris.height * 2), Image.LANCZOS)
    a = np.asarray(gris)
    return np.dstack([a, a, a, np.full(a.shape, 255, np.uint8)])


def guardar_jpg(bgra: np.ndarray, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(bgra[..., 2::-1]).save(ruta, quality=85)


def pid_de_fortnite() -> int | None:
    for p in psutil.process_iter(["name"]):
        if p.info["name"] == FORTNITE:
            return p.pid
    return None


def al_frente(pid: int) -> bool:
    """Si la ventana activa es la de Fortnite: fuera del juego la pantalla puede decir «COFRE» por otra cosa."""
    ventana_activa = ctypes.windll.user32.GetForegroundWindow()
    dueno = ctypes.wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(ventana_activa, ctypes.byref(dueno))
    return dueno.value == pid


def monitor_del_juego(sct) -> dict:
    """El monitor de `config.json` (1, 2...); si no dice, el principal de Windows."""
    if CONFIG["monitor"]:
        return sct.monitors[CONFIG["monitor"]]
    return next((mon for mon in sct.monitors[1:] if mon.get("is_primary")), sct.monitors[1])


class Contador:
    def __init__(self, avisar):
        self.avisar = avisar  # función que recibe el estado para el contador en pantalla
        DATOS.mkdir(exist_ok=True)
        self.f_cofres = DATOS / "cofres.jsonl"
        self.f_premios = DATOS / "premios.jsonl"
        self.f_eventos = DATOS / "eventos.jsonl"
        self.total = self._contar_lineas(self.f_cofres)
        # Lo abierto antes de existir el contador: un estimado, y por eso se muestra aparte del total.
        antes = json.loads((DATOS / "antes.json").read_text(encoding="utf-8")) if (DATOS / "antes.json").exists() else {}
        # Lo de antes del contador = partidas de antes × media de cofres de las partidas registradas.
        # La media se recalcula al terminar cada partida, así que la cifra se afina sola.
        self.partidas_antes: int = antes.get("partidas_antes", 0)
        self.antes_fijo: int = antes.get("cofres_estimados", 0)  # si todavía no hay partidas registradas
        self.por_partida: dict[str, int] = {}
        if self.f_cofres.exists():
            for linea in self.f_cofres.read_text(encoding="utf-8").splitlines():
                if p := json.loads(linea).get("partida"):
                    self.por_partida[p] = self.por_partida.get(p, 0) + 1
        self.partida = partida_actual()
        self.antes = self._base_antes()
        self.artilugios_antes: dict[str, int] = antes.get("artilugios_antes", {})
        # «Hoy»: los cofres del registro con fecha de esta jornada (también los corregidos a mano).
        self.jornada_actual = jornada(datetime.now())
        self.sesion = self._cofres_de(self.jornada_actual)
        self.ultimo_cofre: tuple[int, float] | None = None
        self.ultimo_tipo = ""
        self.fuente_tipo = "aviso"
        self.recien: float | None = None  # cuándo se contó el último cofre, para que el número brille
        self.premio: dict | None = None  # el último premio, para la franja del recuadro
        self.premio_pendiente: tuple[dict, float] | None = None  # premio esperando su cofre (VENTANA_PREMIO)
        self.premios = self._contar_premios()
        # Lo que falta de la semana (semana.json); se marca al salir en un letrero de premio, tuyo o
        # de un compañero, porque el equipo comparte los premios.
        ruta_semana = Path(__file__).parent / "semana.json"
        self.semana = json.loads(ruta_semana.read_text(encoding="utf-8")) if ruta_semana.exists() else None
        self.cosmeticos: set[str] = set()
        if self.f_premios.exists():
            for linea in self.f_premios.read_text(encoding="utf-8").splitlines():
                if clave := json.loads(linea).get("cosmetico"):
                    self.cosmeticos.add(clave)
        # El token sale una vez por cuenta, y el de un compañero también te da el acceso.
        self.token = self.f_premios.exists() and '"token_pirata": true' in self.f_premios.read_text(encoding="utf-8")
        self.premios_vistos: dict[str, tuple[float, str | None]] = {}  # letrero → (última vez, qué premio es)
        self.previo: list[tuple[str, int]] = []  # líneas de cofre de la lectura anterior: (tipo, cuántos)
        self.contados: list[tuple[str, int]] = []  # líneas del aviso en pantalla y cuántos ya se contaron
        self.pe_previo: int | None = None  # los PE de la lectura anterior
        self.pe_aviso: int | None = None  # los PE más altos del aviso en pantalla, leídos dos veces seguidas
        self.aviso_visto = float("-inf")  # última vez que se leyó algo del aviso
        self.zona_xp: np.ndarray | None = None
        # La misión de cofres de espíritu como red: cada subida se empareja con un cofre de espíritu
        # del aviso; si en 3 s no aparece ninguno, se cuenta por la misión.
        self.espiritus_sin_mision: list[float] = []
        self.mision_pendiente: list[float] = []
        self.firma_previa: tuple | None = None
        self.firma_anotada: tuple | None = None
        self.diag_guardadas = 0
        self.mision: int | None = None
        self.mision_candidata: int | None = None
        self.tick = 0
        self.visible = False  # el recuadro se muestra solo con Fortnite al frente
        self.botones: queue.Queue = queue.Queue()  # picadas del botón de roto, de su propio hilo

    @staticmethod
    def _contar_lineas(ruta: Path) -> int:
        if not ruta.exists():
            return 0
        with ruta.open(encoding="utf-8") as f:
            return sum(1 for _ in f)

    def _en_curso(self) -> str | None:
        return self.partida[0] if self.partida and not self.partida[1] else None

    def _media(self) -> float | None:
        """Media de cofres de las partidas registradas que ya terminaron."""
        terminadas = [n for p, n in self.por_partida.items() if p != self._en_curso()]
        return sum(terminadas) / len(terminadas) if terminadas else None

    def _partidas(self) -> int:
        """Las de antes más las registradas, contando la que está en curso aunque aún no abra cofres."""
        registradas = set(self.por_partida)
        if self._en_curso():
            registradas.add(self._en_curso())
        return self.partidas_antes + len(registradas)

    def _base_antes(self) -> int:
        """Partidas de antes × media de las partidas registradas que ya terminaron."""
        media = self._media()
        if not self.partidas_antes or media is None:
            return self.antes_fijo
        return round(self.partidas_antes * media)

    def _estado_semana(self) -> dict | None:
        """Lo que falta de la semana para el recuadro; None cuando la semana ya terminó."""
        if not self.semana or datetime.now().date().isoformat() > self.semana["termina"]:
            return None
        return {
            "titulo": f"TE FALTA · SEMANA {self.semana['semana']} ({self.semana['artista'].upper()})",
            "items": [{"clave": c["clave"], "nombre": c["nombre"], "tienes": c["clave"] in self.cosmeticos} for c in self.semana["faltan"]],
        }

    def _cosmetico_de(self, texto: str) -> dict | None:
        """El cosmético de la semana que nombra el letrero, si es uno de los que faltan."""
        for c in (self.semana or {}).get("faltan", []):
            if any(b in texto for b in c["buscar"]):
                return c
        return None

    def _cofres_de(self, dia) -> int:
        if not self.f_cofres.exists():
            return 0
        filas = (json.loads(l) for l in self.f_cofres.read_text(encoding="utf-8").splitlines())
        return sum(jornada(datetime.fromisoformat(f["fecha"])) == dia for f in filas)

    def _contar_premios(self) -> dict[str, int]:
        """Cuántos de cada premio llevas, del registro. Los de un compañero también cuentan: el equipo
        comparte los premios; quién abrió el cofre queda en «de»."""
        cuenta: dict[str, int] = {}
        if self.f_premios.exists():
            for linea in self.f_premios.read_text(encoding="utf-8").splitlines():
                fila = json.loads(linea)
                clave = fila.get("artilugio") or norm(fila["premio"])
                cuenta[clave] = cuenta.get(clave, 0) + 1
        return cuenta

    @staticmethod
    def _anexar(ruta: Path, datos: dict) -> None:
        with ruta.open("a", encoding="utf-8") as f:
            f.write(json.dumps(datos, ensure_ascii=False) + "\n")

    def evento(self, tipo: str, **datos) -> None:
        self._anexar(self.f_eventos, {"fecha": datetime.now().isoformat(timespec="milliseconds"), "tipo": tipo, **datos})

    def estado(self) -> None:
        self.avisar(
            {
                "total": self.total,
                "antes": self.antes,
                "partidas": self._partidas() if self.partidas_antes else None,
                "media": self._media(),
                "sesion": self.sesion,
                "tipo": self.ultimo_tipo,
                "fuente_tipo": self.fuente_tipo,
                "recien": self.recien,
                "premio": self.premio,
                # Encontrados de cada artilugio: los de antes del contador más los que ha visto él.
                "premios": {k: self.premios.get(k, 0) + self.artilugios_antes.get(k, 0) for k in {*self.premios, *self.artilugios_antes}},
                "token": self.token,
                "semana": self._estado_semana(),
                "visible": self.visible,
            }
        )

    def contar_cofre(self, tipo: str, zona: np.ndarray | None, ahora: float, fuente: str = "aviso") -> None:
        self.total += 1
        if jornada(datetime.now()) != self.jornada_actual:  # pasaron las 6 a. m.: empieza otro día
            self.jornada_actual = jornada(datetime.now())
            self.sesion = 0
        self.sesion += 1
        self.ultimo_cofre = (self.total, ahora)
        self.ultimo_tipo = tipo
        self.fuente_tipo = fuente
        self.recien = ahora
        if tipo == ESPIRITU and fuente == "aviso":
            if self.mision_pendiente:
                self.mision_pendiente.pop(0)  # la misión subió primero: este es su cofre
            else:
                self.espiritus_sin_mision.append(ahora)
        fila = {"n": self.total, "fecha": datetime.now().isoformat(timespec="seconds"), "tipo": tipo}
        # La repetición más nueva es la de esta partida si empezó hace menos de 40 min; si es más vieja,
        # Fortnite no está grabando repeticiones y el cofre queda sin partida (no entra a la media).
        if self.partida and time.time() - self.partida[2] < 2400:
            fila["partida"] = self.partida[0]
            self.por_partida[self.partida[0]] = self.por_partida.get(self.partida[0], 0) + 1
        if zona is not None:
            imagen = DATOS / "cofres" / f"{self.total:05d}.jpg"  # el aviso tal como se leyó, para revisarlo
            guardar_jpg(zona, imagen)
            fila["imagen"] = imagen.name
        if fuente != "aviso":
            fila["fuente"] = fuente
        self._anexar(self.f_cofres, fila)
        print(f"Cofre #{self.total}: {tipo} ({fuente})")
        if self.premio_pendiente and ahora - self.premio_pendiente[1] <= VENTANA_PREMIO:
            premio, _ = self.premio_pendiente  # el letrero salió antes de que se confirmara el cofre
            self.premio_pendiente = None
            self._registrar_premio(premio, self.total, ahora)
        self.estado()

    async def procesar(self, frame: np.ndarray, leer, ahora: float | None = None) -> None:
        """Una lectura de pantalla. `leer` es el OCR: recibe BGRA y devuelve líneas."""
        ahora = time.monotonic() if ahora is None else ahora
        self.tick += 1
        await self._leer_xp(recortar(frame, "xp"), leer, ahora)
        if self.tick % 2 == 0:  # el letrero dura varios segundos y la misión cambia poco
            await self._leer_letrero(frame, leer, ahora)
            await self._leer_mision(recortar(frame, "mision"), leer, ahora)
        # Un premio sin cofre tuyo en VENTANA_PREMIO: lo abrió un compañero, o salió de un cofre roto.
        if self.premio_pendiente and ahora - self.premio_pendiente[1] > VENTANA_PREMIO:
            premio, _ = self.premio_pendiente
            self.premio_pendiente = None
            self._registrar_premio(premio, None, ahora)
        # Una subida de la misión sin su cofre de espíritu en el aviso: el aviso se lo saltó.
        while self.mision_pendiente and ahora - self.mision_pendiente[0] > 3:
            self.mision_pendiente.pop(0)
            zona = self.zona_xp if self.zona_xp is not None else recortar(frame, "xp")
            self.contar_cofre(ESPIRITU, zona, ahora, fuente="misión")
        self.espiritus_sin_mision = [t for t in self.espiritus_sin_mision if ahora - t < 6]

    def _desfase(self, tipos: list[str]) -> int:
        """Si el aviso largo perdió sus primeras líneas al crecer, cuántas perdió; 0 si no es eso."""
        contados = [t for t, _ in self.contados]
        if len(contados) < 5 or len(tipos) < 4:
            return 0
        for k in range(1, len(contados)):
            resto = contados[k:]
            m = min(len(resto), len(tipos))
            if resto[:m] == tipos[:m]:
                return k
        return 0

    async def _leer_xp(self, zona: np.ndarray, leer, ahora: float) -> None:
        crudo = await leer(zona)
        realzado = await leer(realzar(zona))
        # Las líneas de cofre de cada lectura, en el orden del aviso (cada tipo nuevo se agrega abajo, y uno
        # que se repite sube su «X2», «X3»). A veces una lectura corta «COFRE RARO X3» a «COFRE» o a
        # «COFRE RARO», y el número de líneas no cambia por eso: de cada posición vale lo más específico.
        a = [t for t in map(tipo_de_cofre, crudo) if t]
        b = [t for t in map(tipo_de_cofre, realzado) if t]
        if len(a) == len(b):
            lineas = [((y[0] if x[0] == "COFRE" else x[0]), max(x[1], y[1])) for x, y in zip(a, b)]
        else:
            lineas = max(a, b, key=len)
        # Una línea vale cuando dos lecturas seguidas leen el mismo tipo, y de cuántos trae, lo que lean
        # las dos: un error del OCR no se repite igual.
        estable: list[tuple[str, int]] = []
        for (tipo, n), (tipo_previo, n_previo) in zip(lineas, self.previo):
            if tipo != tipo_previo:
                break
            estable.append((tipo, min(n, n_previo)))
        self.previo = lineas
        todas = crudo + realzado
        pe = pe_del_aviso(todas)
        pe_estable = pe if pe is not None and pe == self.pe_previo else None
        self.pe_previo = pe
        hay_pe = any(re.search(r"\d\s*PE\b", norm(l)) for l in todas)
        if lineas or hay_pe:
            self.aviso_visto = ahora
        elif ahora - self.aviso_visto > AVISO_CERRADO:
            self.contados, self.pe_aviso = [], None
        self.zona_xp = zona
        # Un aviso nuevo puede aparecer justo al cerrarse el anterior, sin hueco que lo separe. Se nota
        # porque sus PE bajan (3850 de «RARO X3, ESPÍRITUS» a 900 de otro «RARO», en una bóveda)...
        if pe_estable is not None:
            if self.pe_aviso is not None and pe_estable < self.pe_aviso:
                if self.contados:
                    self.evento("aviso_nuevo_por_pe", antes=self.contados, pe_antes=self.pe_aviso, pe_ahora=pe_estable)
                    self.contados = []
                self.pe_aviso = pe_estable
            else:
                self.pe_aviso = max(self.pe_aviso or 0, pe_estable)
        # ...o porque sus líneas ya no coinciden con las contadas (rara, y luego espíritu).
        if estable and self.contados:
            n = min(len(estable), len(self.contados))
            if [t for t, _ in estable[:n]] != [t for t, _ in self.contados[:n]]:
                desfase = self._desfase([t for t, _ in estable])
                if desfase:
                    self.evento("aviso_recorrido", quitadas=desfase, antes=self.contados, ahora=estable)
                    self.contados = self.contados[desfase:]
                else:
                    self.evento("aviso_nuevo_sin_hueco", antes=self.contados, ahora=estable)
                    self.contados, self.pe_aviso = [], pe_estable
        # Cada línea cuenta lo que creció desde la última vez: una nueva, todos sus cofres; una que pasó de
        # «X2» a «X3», uno.
        for i, (tipo, n) in enumerate(estable):
            ya = self.contados[i][1] if i < len(self.contados) else 0
            for _ in range(n - ya):
                self.contar_cofre(tipo, zona, ahora)
        self.contados = [
            (c[0], max(c[1], e[1])) if c and e else (c or e)
            for c, e in zip_longest(self.contados, estable)
        ]
        if len(estable) >= 6:
            self.evento("aviso_largo", lineas=estable)  # por si Fortnite recorta la lista cuando crece
        if DIAGNOSTICO:
            self._diagnostico(crudo, realzado, zona)

    def _diagnostico(self, crudo: list[str], realzado: list[str], zona: np.ndarray) -> None:
        """Anota cada cambio estable del aviso (sus PE y cuántas líneas trae) con su foto."""

        def resumen(lineas: list[str]) -> tuple[int, int]:
            normas = [norm(l) for l in lineas]
            etiquetas = sum(len(re.findall(r"[A-Z]", n)) >= 6 for n in normas)
            return etiquetas, sum("CONTENEDOR" in n for n in normas)

        etiquetas, contenedor = map(max, zip(resumen(crudo), resumen(realzado)))
        firma = (pe_del_aviso(crudo + realzado), etiquetas, contenedor)
        estable = firma == self.firma_previa
        self.firma_previa = firma
        if not estable or firma == self.firma_anotada or firma == (None, 0, 0):
            return
        self.firma_anotada = firma
        fecha = datetime.now()
        imagen = DATOS / "diagnostico" / f"{fecha:%Y%m%d-%H%M%S-%f}"[:-3]
        guardar_jpg(zona, imagen.with_suffix(".jpg"))
        lineas = list(dict.fromkeys(l for l in crudo + realzado if len(re.findall(r"[A-Za-z]", l)) >= 3))
        self.evento("aviso_pe", pe=firma[0], lineas=lineas, imagen=imagen.name + ".jpg")
        self.diag_guardadas += 1
        if self.diag_guardadas % 100 == 0:
            fotos = sorted((DATOS / "diagnostico").glob("*.jpg"))
            for vieja in fotos[:-DIAG_MAX]:
                vieja.unlink(missing_ok=True)

    async def _leer_letrero(self, frame: np.ndarray, leer, ahora: float) -> None:
        zona = recortar(frame, "letrero")
        lineas = await leer(zona)
        # «ENCONTRASTE» en los artilugios y «HAS ENCONTRADO» en el token: los dos traen «NCONTRA».
        idx = next((i for i, l in enumerate(lineas) if "NCONTRA" in norm(l)), None)
        if idx is None:
            # Si el OCR no leyó el encabezado, el token todavía se reconoce por su propio texto.
            idx = next((i - 1 for i, l in enumerate(lineas) if "TIENDA" in norm(l) and "PIRAT" in norm(" ".join(lineas[i : i + 2]))), None)
            if idx is None:
                return
        # El nombre del premio son las (a lo mucho) dos líneas bajo el encabezado, en mayúsculas. Lo demás
        # es texto del juego que cae en la zona («BUSCAR», «Espacio para pasar…») o basura del OCR («-4»).
        palabras = " ".join(lineas[idx + 1 : idx + 3]).split()
        premio = " ".join(p for p in palabras if re.search(r"[^\W\d_]", p) and p == p.upper())
        clave = norm(premio)
        # Al desvanecerse, el letrero se lee a medias («DE», «A DE», «O»): sin una palabra de tres letras
        # no nombra ningún premio.
        if not re.search(r"[A-Z]{3,}", clave):
            return
        cosmetico = self._cosmetico_de(clave)
        token = "PIRAT" in clave or "TIENDA" in clave  # aunque el OCR se coma alguna letra
        artilugio = "ARTIL" in clave or "ESPIRIT" in clave  # «DE ESPIRITU» cuando se come «ARTILUGIO»
        identidad = "token" if token else cosmetico["clave"] if cosmetico else "artilugio" if artilugio else None
        # El mismo letrero sigue en pantalla unos 6 s y el OCR lo lee cada vez distinto («ARTILVGIO», «DE
        # ESPIRITU», o «DORADA NUEVA FASE DE L» con el aviso de la tormenta pegado). Dentro de 8 s es el mismo
        # premio si el texto dice el mismo premio (dos artilugios también: su texto es idéntico para los
        # cinco); si no dice cuál es, si se parece. Un texto que sí lo dice no se descarta por parecido,
        # para que el token no se pierda detrás de una lectura a medias («ACCESO A LA»).
        for vista, (cuando, identidad_vista) in self.premios_vistos.items():
            if ahora - cuando < 8 and (identidad == identidad_vista if identidad else parecidos(vista, clave)):
                self.premios_vistos[vista] = (ahora, identidad_vista)
                return
        self.premios_vistos = {k: v for k, v in self.premios_vistos.items() if ahora - v[0] < 8}
        self.premios_vistos[clave] = (ahora, identidad)
        fecha = datetime.now()
        imagen = DATOS / "premios" / f"{fecha:%Y%m%d-%H%M%S}.jpg"
        guardar_jpg(recortar(frame, (760, 100, 1800, 900)), imagen)  # letrero con su ícono
        fila = {"fecha": fecha.isoformat(timespec="milliseconds"), "premio": premio, "imagen": imagen.name}
        # El texto es el mismo para los cinco artilugios: cuál fue lo dice el ícono.
        if artilugio:
            clave_art, distancia = artilugios.reconocer(recortar(frame, artilugios.ZONA_ICONO)[..., 2::-1])
            fila["artilugio"] = clave_art
            fila["distancia_icono"] = round(distancia, 3)
        if cosmetico:
            fila["cosmetico"] = cosmetico["clave"]
        # La pantalla completa, de recuerdo: una por tipo de premio, porque los artilugios se repiten. Si la
        # persona borra la de un tipo, se guarda la siguiente que salga. La del token, sin pérdida.
        tipo = "token-pirata" if token else fila.get("cosmetico") or fila.get("artilugio") or (
            "artilugio" if artilugio else re.sub(r"[^a-z0-9]+", "-", clave.lower()).strip("-"))
        if not any((DATOS / "capturas").glob(f"*-{tipo}.*")):
            captura = DATOS / "capturas" / f"{fecha:%Y%m%d-%H%M%S}-{tipo}.{'png' if token else 'jpg'}"
            if token:
                captura.parent.mkdir(parents=True, exist_ok=True)
                Image.fromarray(frame[..., 2::-1]).save(captura)
            else:
                guardar_jpg(frame, captura)
            fila["captura"] = captura.name
        if token:
            fila["token_pirata"] = True
            self.token = True
            for _ in range(3):
                winsound.Beep(880, 250)
        # Es tuyo si abriste un cofre en los VENTANA_PREMIO s de antes; el letrero puede salir antes de que
        # el cofre se confirme, así que se espera lo mismo a que llegue.
        if self.ultimo_cofre and ahora - self.ultimo_cofre[1] <= VENTANA_PREMIO:
            self._registrar_premio(fila, self.ultimo_cofre[0], ahora)
        else:
            if self.premio_pendiente:  # otro premio sin cofre sigue esperando: se registra, no se pisa
                self._registrar_premio(self.premio_pendiente[0], None, ahora)
            self.premio_pendiente = (fila, ahora)
            if fila.get("token_pirata"):  # la alerta no espera
                self.premio = self._franja(fila, None, ahora)
                self.estado()

    def _franja(self, fila: dict, cofre: int | None, ahora: float) -> dict:
        return {
            "nombre": fila["premio"],
            "artilugio": fila.get("artilugio"),
            "cosmetico": fila.get("cosmetico"),
            "cofre": cofre,
            "cuando": ahora,
            "pirata": bool(fila.get("token_pirata")),
        }

    def _registrar_premio(self, fila: dict, cofre: int | None, ahora: float) -> None:
        fila = {**fila, "cofre": cofre, "de": "tuyo" if cofre else "compañero o cofre roto"}
        self._anexar(self.f_premios, fila)
        clave = fila.get("artilugio") or norm(fila["premio"])
        self.premios[clave] = self.premios.get(clave, 0) + 1  # también los de un compañero: se comparten
        if fila.get("cosmetico"):
            self.cosmeticos.add(fila["cosmetico"])
        nombre = estilo.ARTILUGIOS.get(fila.get("artilugio") or "", fila["premio"])
        print(f"Premio: {nombre}  ({f'cofre #{cofre}' if cofre else 'de un compañero o de un cofre roto'})")
        self.premio = self._franja(fila, cofre, ahora)
        self.estado()

    async def _leer_mision(self, zona: np.ndarray, leer, ahora: float) -> None:
        """Vigila la misión de cofres de espíritu: cada subida debe tener su cofre en el aviso."""
        for linea in await leer(zona):
            m = MISION_COFRES.search(norm(linea))
            if not m:
                continue
            valor = int(m.group(1))
            if self.mision is None:
                self.mision = valor
            elif valor != self.mision:
                # El OCR a veces se equivoca en un dígito: el valor nuevo vale al leerlo dos veces seguidas.
                if valor == self.mision_candidata and 0 < valor - self.mision <= 3:
                    self.evento("mision_espiritus", antes=self.mision, ahora=valor)
                    for _ in range(valor - self.mision):
                        if self.espiritus_sin_mision:
                            self.espiritus_sin_mision.pop(0)  # el aviso ya lo contó
                        else:
                            self.mision_pendiente.append(ahora)
                    self.mision = valor
                self.mision_candidata = valor
            return

    async def correr(self) -> None:
        import ocr  # el motor de WinRT se crea en este hilo

        with mss.MSS() as sct:
            mon = monitor_del_juego(sct)
            print(f"Mirando el monitor de {mon['width']}x{mon['height']}. Cofres registrados: {self.total}")
            pid, revisado = None, float("-inf")
            while True:
                inicio = time.monotonic()
                if inicio - revisado > 5:  # buscar el proceso cuesta: cada 5 s basta
                    nuevo = pid_de_fortnite()
                    if nuevo and nuevo != pid:
                        self.evento("fortnite_abierto", pid=nuevo)
                    pid, revisado = nuevo, inicio
                    partida = partida_actual()
                    if partida != self.partida:  # empezó o terminó una partida: se recalcula lo de antes
                        self.partida = partida
                        antes, self.antes = self.antes, self._base_antes()
                        if self.antes != antes:
                            self.evento("base_antes", antes=antes, ahora=self.antes, partidas=len(self.por_partida))
                        self.estado()
                jugando = pid is not None and al_frente(pid)
                if jugando != self.visible:
                    self.visible = jugando
                    self.previo = []  # al volver, una línea necesita otra vez dos lecturas seguidas
                    self.estado()
                # El botón de roto: cuenta solo con Fortnite al frente; fuera del juego se descarta.
                while not self.botones.empty():
                    self.botones.get_nowait()
                    if jugando:
                        self.contar_cofre(ROTO, None, time.monotonic(), fuente="botón")
                        winsound.Beep(1400, 60)  # para saber que entró sin quitar la vista del juego
                    else:
                        self.evento("boton_fuera_del_juego")
                if not jugando:
                    await asyncio.sleep(1)
                    continue
                frame = np.asarray(sct.grab(mon))
                try:
                    await self.procesar(frame, ocr.leer)
                except Exception as e:  # una lectura fallida no debe tumbar el contador
                    self.evento("error", detalle=repr(e))
                await asyncio.sleep(max(0, PERIODO - (time.monotonic() - inicio)))


def ventana(cola: queue.Queue, mon: dict) -> None:
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.94)
    clave = "#%02x%02x%02x" % estilo.TRANSPARENTE
    root.configure(bg=clave)
    root.attributes("-transparentcolor", clave)  # las esquinas del panel redondeado
    # De fábrica, a la izquierda a media altura en 2560x1440: debajo del panel de espíritus del inventario
    # (termina en ~440), encima de los avisos de eliminaciones (empiezan en ~770, y el recuadro con premio
    # llega a ~745) y fuera de las zonas que se leen. Se mueve con «posicion_recuadro».
    x, y = CONFIG["posicion_recuadro"]
    root.geometry(f"+{mon['left'] + x}+{mon['top'] + y}")
    lienzo = tk.Label(root, bd=0, bg=clave)
    lienzo.pack()
    actual: dict = {"e": None, "foto": None, "efectos": None}

    def atravesable():
        """Que los clics pasen de largo hacia el juego: así no se puede cerrar ni mover por accidente."""
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        exstyle = ctypes.windll.user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
        # WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW (fuera de Alt+Tab) | WS_EX_NOACTIVATE
        ctypes.windll.user32.SetWindowLongW(hwnd, -20, exstyle | 0x80000 | 0x20 | 0x80 | 0x08000000)

    def pintar(e: dict, ahora: float) -> None:
        actual["foto"] = ImageTk.PhotoImage(estilo.dibujar(e, ahora))  # se guarda: si no, Tk la suelta
        lienzo.config(image=actual["foto"])

    def efectos(e: dict, ahora: float) -> tuple:
        """Lo que cambia solo con el tiempo: el brillo del número y la franja del premio."""
        recien = e.get("recien") is not None and ahora - e["recien"] < estilo.DURA_RECIEN
        p = e.get("premio")
        franja = bool(p) and (p.get("pirata") or ahora - p["cuando"] < estilo.DURA_PREMIO)
        return recien, franja

    def refrescar():
        ahora = time.monotonic()
        nuevo = None
        try:
            while True:
                nuevo = cola.get_nowait()
        except queue.Empty:
            pass
        if nuevo is not None:
            actual["e"] = nuevo
            if nuevo["visible"]:
                pintar(nuevo, ahora)
                root.deiconify()
                atravesable()
            else:
                root.withdraw()
            actual["efectos"] = efectos(nuevo, ahora)
        elif actual["e"] is not None and actual["e"]["visible"]:
            ef = efectos(actual["e"], ahora)
            if ef != actual["efectos"]:  # se apagó el brillo o terminó la franja: se repinta
                actual["efectos"] = ef
                pintar(actual["e"], ahora)
        root.attributes("-topmost", True)
        root.after(250, refrescar)

    root.withdraw()  # aparece cuando Fortnite esté al frente
    refrescar()
    root.mainloop()


def escuchar_boton(contador: "Contador") -> None:
    """Atiende la tecla de roto en todo Windows; el contador decide si cuenta (solo con Fortnite al frente)."""
    if TECLA_ROTO is None:  # sin botón: los cofres rotos no se cuentan
        return
    user32 = ctypes.windll.user32
    if not user32.RegisterHotKey(None, 1, 0x4000, TECLA_ROTO):  # 0x4000: sin repetición al mantenerla
        contador.evento("error", detalle="no se pudo registrar la tecla del botón de roto")
        return
    msg = ctypes.wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        if msg.message == 0x0312:  # WM_HOTKEY
            contador.botones.put(time.monotonic())


def main() -> None:
    # Una sola copia: dos contadores a la vez contarían cada cofre dos veces.
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    candado = kernel32.CreateMutexW(None, False, "Local\\contador-cofres-fortnite")  # vive hasta que el proceso termine
    if ctypes.get_last_error() == 183 or not candado:  # 183: ERROR_ALREADY_EXISTS
        return
    cola: queue.Queue = queue.Queue()
    contador = Contador(cola.put)
    threading.Thread(target=lambda: asyncio.run(contador.correr()), daemon=True).start()
    threading.Thread(target=escuchar_boton, args=(contador,), daemon=True).start()
    with mss.MSS() as sct:
        mon = monitor_del_juego(sct)
    ventana(cola, mon)


if __name__ == "__main__":
    main()
