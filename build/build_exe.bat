@echo off
echo ======================================================================
echo Packaging PortHole 98 into standalone Windows executable...
echo ======================================================================

cd /d "%~dp0\.."

pyinstaller --noconfirm --onefile --windowed ^
    --name PortHole98 ^
    --icon "build\icon.ico" ^
    --add-data "web;web" ^
    desktop.py

if %ERRORLEVEL% equ 0 (
    echo.
    echo ======================================================================
    echo Build successful! Executable generated at: dist\PortHole98.exe
    echo ======================================================================
) else (
    echo.
    echo Build failed with error code %ERRORLEVEL%.
)
