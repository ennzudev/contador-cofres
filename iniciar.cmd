@echo off
rem Sin consola. Si ya hay un contador corriendo, este se cierra solo.
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0contador.py"
