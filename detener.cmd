@echo off
rem Cierra el contador de cofres. Para volver a abrirlo: iniciar.cmd (o reiniciar la PC).
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*contador.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; exit 0"
