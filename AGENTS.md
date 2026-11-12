# AGENTS.md

Instrucciones para el agente que instala o atiende el contador de cofres en la PC de alguien. Qué hace
el programa y qué es cada archivo de configuración: [`README.md`](README.md). Léelo primero.

## Reglas

- **`datos/` es el registro de la persona: no se borra ni se edita sin preguntarle.** Si hay que
  corregir algo, primero un respaldo (`datos/cofres.antes-de-<motivo>.jsonl`).
- **`config.json`, `semana.json` y `datos/` no van al repo** (están en `.gitignore`). Lo de cada persona
  se cambia ahí, nunca en el código ni en `ejemplos/`.
- **No se reinicia el contador a media partida.** Antes de detenerlo o reiniciarlo, revisa si Fortnite
  está abierto (`FortniteClient-Win64-Shipping.exe`) y la repetición más nueva de
  `%LOCALAPPDATA%\FortniteGame\Saved\Demos`. Si se escribió en los últimos minutos, hay partida en curso:
  espera.
- **Una prueba de la tecla de rotos con Fortnite al frente cuenta un cofre real.** Después se quita esa
  fila de `datos/cofres.jsonl`, con permiso de la persona.

## Instalación

Haz las preguntas de una en una y escribe cada respuesta en su archivo en cuanto llegue.

### 1. La PC

1. **Python 3.10 a 3.13:** `py -3 --version` o `python --version`. Si no hay, instala el 3.13 con
   `winget install -e --id Python.Python.3.13`.
2. **El entorno**, dentro de la carpeta del repo (con `python` en lugar de `py -3` si no hay `py`):
   ```
   py -3 -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```
3. **El OCR en español de México.** Esto lista los idiomas que tiene:
   ```powershell
   [Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime] | Out-Null
   [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages | ForEach-Object LanguageTag
   ```
   Si no aparece `es-MX`, se instala desde una PowerShell como administrador:
   ```powershell
   Get-WindowsCapability -Online | Where-Object Name -Like 'Language.OCR*es-MX*' | Add-WindowsCapability -Online
   ```
   Si la persona no puede abrirla como administrador, otro camino es agregar el idioma «Español (México)»
   en Configuración › Hora e idioma › Idioma.
4. **Las pruebas:** las tres de la sección «Pruebas» del README. Cada una termina con su cuenta
   (por ejemplo, «13/13 casos bien»), y las dos cifras deben ser iguales.

### 2. Fortnite

En `%LOCALAPPDATA%\FortniteGame\Saved\Config\WindowsClient\GameUserSettings.ini`:

- `ResolutionSizeX` y `ResolutionSizeY`: la resolución del juego. Si no es 16:9, avisa que habrá que
  ajustar las zonas (paso 5).
- `PreferredFullscreenMode`: `1` es pantalla completa en ventana, la que sirve. Con otro valor, pídele
  que lo cambie en la configuración de video de Fortnite.

Pregúntale además:

1. **¿Fortnite está en español (Latinoamérica)?** El contador lee los textos en español.
2. **¿Tiene prendida la opción de grabar repeticiones?** Sin ella el contador cuenta igual, pero no saca
   el promedio por partida.

### 3. Lo que lleva de la minitemporada → `datos/antes.json`

Parte de `ejemplos/antes.json`. Pregúntale:

1. **¿Cuántas partidas lleva desde que empezó la minitemporada?** Va en `partidas_antes`.
2. **¿Cuántos cofres calcula que ha abierto?** Va en `cofres_estimados`. Solo se muestra mientras no
   haya una partida registrada; después, el contador lo calcula con su promedio.
3. **Los artilugios de espíritu:** cuántos tiene en el inventario y cuántos ha usado, de cada uno de los
   cinco (acelerador de extracción, extractor portátil, fuego artificial dorado, localizador de espíritus
   y localizador de suerte). Lo más fácil es una captura de su inventario. En `artilugios_antes` va la
   suma de los dos.

### 4. La semana → `semana.json`

Pregúntale **qué premios de la semana en curso ya tiene**. En `semana.json` van solo los que le faltan,
con el número de semana, el artista y el día en que termina. El formato está en `ejemplos/semana.json`.

- Si le falta algo que no tiene ícono en `assets/`, el recuadro pone el del cofre en su lugar. Para
  ponerle el suyo, bájalo de fortnite-api.com (con `language=es-419`, que da los nombres como salen en el
  juego), guárdalo en `assets/originales/<clave>.png` y corre
  `.venv\Scripts\python.exe preparar_assets.py <clave>`.
- `buscar` lleva palabras del nombre del premio tal como sale en el letrero, en mayúsculas y sin acentos.
  El letrero puede nombrarlo distinto que la tienda: el Cadillac de la semana 2 sale como «CALCOMANÍA
  DORADA PARA AUTO». Si un premio sale y no se marca, su letrero está en `datos/premios/`: agrega a
  `buscar` lo que dice.

### 5. Su PC → `config.json`

Escribe solo las claves que cambien de `ejemplos/config.json`. Pregúntale:

1. **La tecla de los cofres rotos.** Si su mouse tiene botones de sobra y su programa (Razer Synapse,
   Logitech G Hub...) deja asignarles una tecla, lo mejor es F13 a F24, porque no existen en el teclado
   y no chocan con el juego. Si no, una tecla que no use en Fortnite, sabiendo que mientras el contador
   corre esa tecla deja de llegarle al juego. O `null`, y no se cuentan.
2. **El monitor**, si tiene más de uno y no juega en el principal.
3. **¿Lo quiere arrancando con Windows?** (paso 6).

Para la primera partida, pon `"diagnostico": true`.

La posición del recuadro de fábrica está pensada para 2560x1440, entre el panel de espíritus del
inventario y los avisos de eliminaciones. El recuadro no se escala (mide unos 430x290 px), así que en una
pantalla más chica ocupa más: después de la primera partida, que la persona diga si le estorba y muévelo
con `posicion_recuadro`.

### 6. Arranque

Con Windows, un acceso directo en la carpeta de Inicio (cambia `<carpeta>` por la ruta del repo):

```powershell
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut("$([Environment]::GetFolderPath('Startup'))\Contador de cofres.lnk")
$lnk.TargetPath = "<carpeta>\.venv\Scripts\pythonw.exe"
$lnk.Arguments = '"<carpeta>\contador.py"'
$lnk.WorkingDirectory = "<carpeta>"
$lnk.Save()
```

Para prenderlo ahora: `iniciar.cmd`. Comprueba que el proceso siga vivo unos segundos después (un
`pythonw.exe` con `contador.py` en su línea de comandos). Si se cierra solo, corre
`.venv\Scripts\python.exe contador.py` en una consola para ver el error.

### 7. Después de la primera partida

Revisa con la persona:

- **El conteo:** las filas de `datos/cofres.jsonl` contra los cofres que ella recuerde abrir.
  `datos/cofres/` guarda la foto del aviso de cada cofre.
- **Si no contó nada,** mira las fotos de `datos/diagnostico/`. Si el aviso de experiencia sale cortado
  o fuera de la foto, la zona `xp` no le queda: ajústala en `config.json` (`zonas`, en coordenadas de
  2560x1440) hasta que el aviso quede entero en la foto.
- **Los errores:** las filas `"tipo": "error"` de `datos/eventos.jsonl`.

Cuando cuente bien, regresa `diagnostico` a `false`: guarda hasta 1500 fotos.

## Cada semana

Cuando termina una semana, pregúntale qué premios de la nueva ya tiene y reescribe `semana.json` (paso 4).

## Actualizar el programa

`git pull` en la carpeta del repo, y reinicia el contador (`detener.cmd` y luego `iniciar.cmd`) sin
partida en curso. Si cambió `requirements.txt`, antes:
`.venv\Scripts\python.exe -m pip install -r requirements.txt`.
