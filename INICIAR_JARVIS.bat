@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Jarvis
set PYTHONUTF8=1
if not exist .venv\Scripts\python.exe (
  echo Primero ejecuta INSTALAR.bat
  pause
  exit /b 1
)
.venv\Scripts\python -m jarvis_core
echo.
echo Jarvis se cerro. Si fue por un error, mira la carpeta logs.
pause
