@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Probar microfono y voz de Jarvis
set PYTHONUTF8=1
if not exist .venv\Scripts\python.exe (
  echo Primero ejecuta INSTALAR.bat
  pause
  exit /b 1
)
.venv\Scripts\python herramientas\probar_audio.py
