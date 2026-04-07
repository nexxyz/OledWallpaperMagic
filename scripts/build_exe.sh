#!/bin/bash
# Build script for OledWallpaperMagic - creates standalone exe with PyInstaller
# Usage: ./scripts/build_exe.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_DIR/dist"

echo "=== OledWallpaperMagic Build Script ==="
echo "Project directory: $PROJECT_DIR"
echo ""

# Check Python version
python_version=$(python -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "Python version: $python_version"

# Install build dependencies
echo "Installing build dependencies..."
pip install --quiet pyinstaller pillow

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf "$DIST_DIR"
rm -rf "$PROJECT_DIR/build"
rm -rf "$PROJECT_DIR/*.spec"

# Get icon path if it exists
ICON_ARG=""
if [ -f "$PROJECT_DIR/icons/icon.ico" ]; then
    ICON_ARG="--icon=$PROJECT_DIR/icons/icon.ico"
    echo "Using icon: $PROJECT_DIR/icons/icon.ico"
fi

# Build exe
echo "Building executable..."
pyinstaller \
    --clean \
    --name "OledWallpaperMagic" \
    --onefile \
    --windowed \
    --add-data "$PROJECT_DIR/icons;icons" \
    --add-data "$PROJECT_DIR/presets;presets" \
    --collect-all typer \
    --collect-all click \
    --collect-all rich \
    --collect-all pydantic \
    --collect-all tomli_w \
    --collect-all shellingham \
    --hidden-import=PySide6 \
    --hidden-import=PySide6.QtCore \
    --hidden-import=PySide6.QtGui \
    --hidden-import=PySide6.QtWidgets \
    $ICON_ARG \
    "$PROJECT_DIR/src/oled_wallpaper_magic/__main__.py"

echo ""
echo "=== Build Complete ==="
echo "Output file: $DIST_DIR/OledWallpaperMagic.exe"
echo ""

# Show size
if [ -f "$DIST_DIR/OledWallpaperMagic.exe" ]; then
    du -sh "$DIST_DIR/OledWallpaperMagic.exe"
fi
