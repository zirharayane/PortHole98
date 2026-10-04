@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0\.."

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo ======================================================================
echo Step 1: Running PyInstaller build (build/build.py)...
echo ======================================================================
"%PYTHON_EXE%" build\build.py
if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller build failed.
    exit /b %errorlevel%
)

echo.
echo ======================================================================
echo Step 2: Compiling Windows installer with Inno Setup...
echo ======================================================================

set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
) else if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
) else if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" (
    set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
) else (
    for %%P in (ISCC.exe) do (
        if not "%%~$PATH:P"=="" set "ISCC=%%~$PATH:P"
    )
)

if not defined ISCC (
    echo Inno Setup not found. Download it free from https://jrsoftware.org/isdl.php then re-run this script.
    exit /b 1
)

echo Using Inno Setup: "!ISCC!"
"!ISCC!" "build\installer.iss"
if errorlevel 1 (
    echo.
    echo [ERROR] Inno Setup compilation failed.
    exit /b %errorlevel%
)

echo.
echo ======================================================================
echo Done. Installer at dist/PortHole98-Setup.exe
echo ======================================================================
