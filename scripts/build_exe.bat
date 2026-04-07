@echo off
REM Build script for OledWallpaperMagic - Windows version
REM Usage: scripts\build_exe.bat

echo === OledWallpaperMagic Build Script ===
echo.

REM Install build dependencies
echo Installing build dependencies...
pip install --quiet pyinstaller pillow
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    exit /b 1
)

REM Clean previous builds
echo Cleaning previous builds...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
if exist "*.spec" del /q "*.spec"

REM Get icon path if it exists
set ICON_ARG=
if exist "icons\icon.ico" set ICON_ARG=--icon=icons\icon.ico

REM Build exe
echo Building executable...
pyinstaller --name "OledWallpaperMagic" --onedir --windowed --add-data "icons;icons" %ICON_ARG% src\oled_wallpaper_magic\__main__.py

echo.
echo === Build Complete ===
echo Output directory: dist\OledWallpaperMagic
