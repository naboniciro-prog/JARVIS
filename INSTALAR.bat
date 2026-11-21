@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Instalando Jarvis
echo ============================================
echo   Instalando Jarvis (solo la primera vez)
echo ============================================
echo.

where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")

%PY% --version >nul 2>nul
if errorlevel 1 (
  echo No encontre Python.
  echo Instala Python 3.12 desde https://www.python.org/downloads/
  echo y marca la casilla "Add Python to PATH" al instalar.
  pause
  exit /b 1
)

if not exist .venv (
  echo Creando entorno...
  %PY% -m venv .venv
)

echo Instalando librerias, puede tardar unos minutos...
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Hubo un error instalando. Saca una foto de esta pantalla y mandamela.
  pause
  exit /b 1
)

echo Descargando la palabra de activacion "Hey Jarvis"...
.venv\Scripts\python -c "import openwakeword.utils as u; u.download_models(model_names=['hey_jarvis'])"

if not exist .env copy .env.example .env >nul
echo.
echo Ahora se abre el archivo .env: pega tu clave de la IA despues de ANTHROPIC_API_KEY=
echo guarda (Ctrl+G o Ctrl+S) y cerra el Bloc de notas.
notepad .env

echo.
echo ============================================
echo   Listo. Para arrancar: INICIAR_JARVIS.bat
echo   Para probar el microfono: PROBAR_MICROFONO.bat
echo ============================================
pause
