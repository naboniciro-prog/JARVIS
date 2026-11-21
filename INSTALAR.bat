@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Instalando Jarvis
echo ============================================
echo   Instalando Jarvis (solo la primera vez)
echo ============================================
echo.

set "PY312=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%PY312%" (set "PY="%PY312%"" & goto tengo_python)
py -3.12 --version >nul 2>nul
if not errorlevel 1 (set "PY=py -3.12" & goto tengo_python)

echo No encontre Python 3.12. Lo instalo solo, espera...
echo (si aparece una ventana pidiendo permiso, apreta "Si")
winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
if exist "%PY312%" (set "PY="%PY312%"" & goto tengo_python)

echo.
echo No pude instalar Python solo.
echo Abri la Microsoft Store, busca "Python 3.12", instalalo
echo y despues volve a abrir INSTALAR.bat
pause
exit /b 1

:tengo_python
echo Python encontrado.

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
