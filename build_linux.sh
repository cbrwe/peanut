#!/usr/bin/env bash
# Peanut Linux build
# ==================
# Produces dist/Peanut/ (folder distribution) and a tarball.
# If appimagetool is on PATH, also produces an AppImage.
#
# Prerequisites:
#   pip install -r requirements.txt
#   pip install -r requirements-build.txt

set -e

APP_NAME="Peanut"
APP_VERSION="1.0.0"

cd "$(dirname "$0")"

echo "──────────────────────────────────────────"
echo " Building ${APP_NAME} for Linux"
echo "──────────────────────────────────────────"

rm -rf build dist
echo "✓ Cleaned previous builds"

if [ ! -f "static/icon.png" ]; then
    echo "✗ static/icon.png missing — can't proceed"
    exit 1
fi

echo "→ Running PyInstaller..."
pyinstaller peanut.spec --clean --noconfirm

if [ ! -d "dist/${APP_NAME}" ]; then
    echo "✗ Build failed — dist/${APP_NAME} not produced"
    exit 1
fi
echo "✓ Built dist/${APP_NAME}/ ($(du -sh "dist/${APP_NAME}" | cut -f1))"

# Tarball — universal Linux distribution
ARCH=$(uname -m)
TARBALL="dist/${APP_NAME}-${APP_VERSION}-linux-${ARCH}.tar.gz"
tar -czf "$TARBALL" -C dist "${APP_NAME}"
echo "✓ Created ${TARBALL}"

# AppImage (optional — only if appimagetool is available)
if command -v appimagetool &> /dev/null; then
    echo "→ Building AppImage..."
    APPDIR="dist/${APP_NAME}.AppDir"
    rm -rf "$APPDIR"
    mkdir -p "$APPDIR/usr/bin"
    cp -r "dist/${APP_NAME}/." "$APPDIR/usr/bin/"

    cat > "$APPDIR/AppRun" << 'APPRUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/Peanut" "$@"
APPRUN
    chmod +x "$APPDIR/AppRun"

    cat > "$APPDIR/peanut.desktop" << DESKTOP
[Desktop Entry]
Name=${APP_NAME}
Exec=Peanut
Icon=peanut
Type=Application
Categories=Utility;
DESKTOP

    cp static/icon.png "$APPDIR/peanut.png"

    APPIMG="dist/${APP_NAME}-${APP_VERSION}-${ARCH}.AppImage"
    appimagetool "$APPDIR" "$APPIMG"
    echo "✓ Created ${APPIMG}"
else
    echo "⚠ Skipping AppImage (install appimagetool to enable)"
    echo "  https://github.com/AppImage/AppImageKit/releases"
fi

echo
echo "──────────────────────────────────────────"
echo " Build complete!"
echo "──────────────────────────────────────────"
ls -lh dist/*.tar.gz dist/*.AppImage 2>/dev/null || true
echo "──────────────────────────────────────────"
