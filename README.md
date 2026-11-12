# Contador de cofres

Cuenta los cofres que abres en Fortnite durante la minitemporada «Caza del tesoro» y te dice qué
probabilidad llevas de sacar el **Token pirata** (acceso a la Tienda pirata). Un recuadro sobre el juego
muestra:

- el total de cofres, con los de antes del contador, y los de hoy;
- tus partidas y cuántos cofres abres en promedio por partida;
- los artilugios de espíritu que has encontrado;
- la probabilidad acumulada del token (1 en 137,500 por cofre, según una tabla de terceros: Epic no la
  publica);
- lo que te falta de los premios de la semana.

Solo mira la pantalla, como OBS: lee el aviso de experiencia («+600 PE / COFRE RARO») y el letrero de
premio con el OCR de Windows. No lee la memoria del juego ni se mete en él.

## Instalarlo

Pásale este repo a tu agente (Claude Code, Codex...) y pídele: **«instálame el contador de cofres»**.
Las instrucciones para él están en [`AGENTS.md`](AGENTS.md): revisa tu PC, te pregunta lo que lleva
el juego (partidas, artilugios, premios de la semana) y deja el contador arrancando con Windows.

### Lo que necesita

- Windows 10 u 11, con Python 3.10 a 3.13.
- Fortnite en **español (Latinoamérica)** y en **pantalla completa en ventana**, que es como está
  probado. En pantalla completa exclusiva, el recuadro puede no verse encima del juego.
- Una pantalla 16:9. Está probado en 2560x1440, y en 1920x1080 las zonas se escalan solas. Con otra
  proporción, o con otra escala del HUD, hay que ajustar las zonas (`zonas`, abajo).
- El OCR de Windows en español de México (`es-MX`). Viene con el idioma español de México.
- La opción de Fortnite de **grabar repeticiones**, prendida. Cada partida deja su repetición, y así el
  contador sabe a qué partida va cada cofre y saca tu promedio por partida.

## Cómo se usa

- **Arranca solo con Windows** y espera. Lee la pantalla solo con Fortnite abierto y al frente; fuera
  del juego, el recuadro se esconde.
- **Los cofres que abres se cuentan solos:** normales, raros y de espíritus. Las cajas de munición, de
  alimentos y los barriles no cuentan.
- **Los cofres rotos se cuentan con una tecla** (`tecla_roto`), porque al romper un cofre (con una
  estructura, un barril o un barco) Fortnite no muestra nada en pantalla. Lo cómodo es un botón del mouse
  mapeado a F13, una tecla que no existe en el teclado. Suena un pitido cuando entra.
- **Antes de ver una repetición, apágalo** con `detener.cmd`: la repetición se ve igual que el juego y
  contaría sus cofres. Para prenderlo otra vez, `iniciar.cmd`.
- **La primera vez que sale cada premio** (cada artilugio, cada cosa de la semana y el token), guarda
  una captura de la pantalla completa en `datos/capturas/`, de recuerdo, con el nombre del premio. Los
  artilugios se repiten, pero se guarda una sola de cada uno. Si borras una, se guarda la siguiente que
  salga.
- **Si sale el token,** suenan tres pitidos y el recuadro se pinta de dorado.

## Qué es tuyo y qué es del repo

El código es de todos. Lo tuyo vive en tres lugares que **no van al repo**, así que un `git pull`
actualiza el programa sin tocar tu configuración ni tus datos:

| Archivo | Qué guarda |
|---|---|
| `config.json` | lo de tu PC: monitor, tecla, posición del recuadro (abajo) |
| `semana.json` | lo que te falta de la semana; se cambia cada semana |
| `datos/` | tu registro: cofres, premios, fotos y lo que llevabas antes (`antes.json`) |

### `config.json`

Lleva solo lo que cambie de los valores de `ejemplos/config.json`. Si no existe, valen todos esos.

| Clave | De fábrica | Qué es |
|---|---|---|
| `monitor` | `null` | el monitor del juego: `1`, `2`...; `null` es el principal de Windows |
| `posicion_recuadro` | `[30, 452]` | dónde va el recuadro, en píxeles desde la esquina del monitor |
| `tecla_roto` | `"F13"` | la tecla de los cofres rotos: `"F1"` a `"F24"`, o `null` para no usarla. Mientras el contador corre, esa tecla ya no le llega a ningún programa |
| `idioma_ocr` | `"es-MX"` | el idioma del OCR de Windows |
| `diagnostico` | `false` | guarda cada cambio del aviso de experiencia con su foto en `datos/diagnostico/`; sirve para revisar una PC nueva |
| `zonas` | `{}` | corrige dónde lee: `xp` (el aviso), `letrero` (el premio), `mision` y `icono`, como `[x0, y0, x1, y1]` en una pantalla de 2560x1440. Los valores de fábrica están en `contador.py` (`ZONAS`) y en `artilugios.py` (`ZONA_ICONO`) |

### `datos/antes.json`

Lo que llevabas antes de instalar el contador. El ejemplo está en `ejemplos/antes.json`.

| Clave | Qué es |
|---|---|
| `partidas_antes` | partidas jugadas en la minitemporada antes del contador. Los cofres de antes salen de multiplicarlas por tu promedio de cofres por partida, que se afina solo con cada partida registrada |
| `cofres_estimados` | los cofres de antes que se muestran mientras no haya ninguna partida registrada |
| `artilugios_antes` | los artilugios encontrados antes del contador: los que tienes en el inventario más los que ya usaste |

### `semana.json`

Lo que te falta de los premios de la semana, con su fecha de cierre. Cuando sale uno en un letrero de
premio, tuyo o de un compañero, se enciende con palomita. El ejemplo de la semana 2 (Lil Uzi Vert) está
en `ejemplos/semana.json`. En cada cosa, `clave` es el nombre de su ícono en `assets/` y `buscar` son los
textos del letrero que la identifican.

## Pruebas

Con el entorno del contador:

```
.venv\Scripts\python.exe pruebas\test_cofres.py
.venv\Scripts\python.exe pruebas\test_premios.py
.venv\Scripts\python.exe pruebas\test_partidas.py
```

Usan un OCR falso y no tocan `datos/`.
