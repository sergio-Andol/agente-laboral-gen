@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  Agente Laboral Gen
echo ============================================
echo.

rem --- 1. Detectar Python (py -3 primero, python como fallback) --------
where py >nul 2>nul
if %errorlevel% neq 0 goto :check_python
set "PYCMD=py -3"
goto :python_ok

:check_python
where python >nul 2>nul
if %errorlevel% neq 0 goto :no_python
set "PYCMD=python"
goto :python_ok

:no_python
echo No se encontro Python. Instala Python 3.11 o superior desde
echo python.org y volve a abrir este archivo.
echo.
echo IMPORTANTE: al instalar, tildar la casilla "Add python.exe to PATH".
echo.
pause
exit /b 1

:python_ok
echo Python encontrado: %PYCMD%
echo.

rem --- 2. Entorno virtual: crear si no existe, reusar si existe --------
if exist ".venv\Scripts\python.exe" goto :venv_ready
echo Creando entorno virtual local ^(.venv^)... primera vez, puede tardar.
%PYCMD% -m venv .venv
if errorlevel 1 (
    echo [ERROR] No se pudo crear el entorno virtual .venv.
    pause
    exit /b 1
)
goto :instalar_deps

:venv_ready
echo Entorno virtual .venv ya existe, se reusa.

:instalar_deps
echo.
echo Instalando/actualizando dependencias...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Fallo la instalacion de dependencias. Revisa el mensaje de arriba.
    pause
    exit /b 1
)

rem --- 3. Bumeran opcional: solo preguntar si no esta ya disponible ----
echo.
echo Verificando soporte opcional para Bumeran ^(Playwright/Chromium^)...
".venv\Scripts\python.exe" -c "from playwright.sync_api import sync_playwright; n=sync_playwright().start(); b=n.chromium.launch(); b.close(); n.stop()" >nul 2>nul
if %errorlevel%==0 goto :bumeran_listo

echo.
echo Bumeran es una fuente de busqueda OPCIONAL ademas de Computrabajo.
echo Requiere descargar el navegador Chromium ^(~300MB^), puede tardar
echo varios minutos segun tu conexion. Si decis que no, la app funciona
echo igual, solo con Computrabajo.
echo.
set /p RESP=Queres instalar soporte opcional para Bumeran? Puede tardar y descargar Chromium. [S/N]:
if /i "%RESP%"=="S" goto :instalar_bumeran
if /i "%RESP%"=="SI" goto :instalar_bumeran
echo.
echo Se omite Bumeran por ahora. La app sigue funcionando con Computrabajo.
echo Si despues cambias de opinion, volve a abrir este archivo y respondes S.
goto :bumeran_listo

:instalar_bumeran
echo.
echo Instalando playwright...
".venv\Scripts\python.exe" -m pip install playwright
if errorlevel 1 (
    echo [ERROR] Fallo instalar playwright. Bumeran no va a estar disponible,
    echo pero la app funciona igual con Computrabajo.
    goto :bumeran_listo
)
echo.
echo Descargando el navegador Chromium ^(puede tardar varios minutos^)...
".venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 (
    echo [ERROR] Fallo la descarga de Chromium. Bumeran no va a estar
    echo disponible, pero la app funciona igual con Computrabajo.
)

:bumeran_listo
rem --- 4. Iniciar la app -------------------------------------------------
echo.
echo ============================================
echo  Agente Laboral Gen esta iniciado. Para cerrar la app, cerra esta
echo  ventana o presiona Ctrl+C.
echo ============================================
echo El navegador se abre solo en unos segundos en:
echo   http://localhost:8501
echo.

".venv\Scripts\python.exe" -m streamlit run ui\app.py --server.port 8501

echo.
echo La app se cerro.
pause
