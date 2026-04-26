#!/usr/bin/env bash
# Peanut Mac build
# ================
# Produces dist/Peanut.app and dist/Peanut-{version}.dmg
#
# Prerequisites:
#   pip install -r requirements.txt        # includes pywebview + pyobjc
#   pip install -r requirements-build.txt  # PyInstaller
#
# IMPORTANT: PyInstaller must run on the same OS as the target.
# This script must be run on macOS to produce a Mac .app — you cannot
# build a Mac binary from a Linux or Windows machine.
#
# Native drag-and-drop:
#   The bundled app uses pywebview, which provides a real native window
#   (not a browser tab) and gives JavaScript real filesystem paths from
#   drag-and-drop events. This is the entire point of going native — a
#   browser-based bundle would have the same drag-and-drop limitations
#   as opening localhost in Safari.
#
# Optional environment variables (for signed distribution):
#   DEVELOPER_ID           "Developer ID Application: Your Name (TEAMID)"
#   APPLE_ID               your.apple.id@example.com
#   APPLE_TEAM_ID          ABCDE12345
#   APPLE_PASSWORD         app-specific password from appleid.apple.com

set -e

APP_NAME="Peanut"
APP_VERSION="1.0.0"
DMG_NAME="${APP_NAME}-${APP_VERSION}.dmg"

cd "$(dirname "$0")"

echo "──────────────────────────────────────────"
echo " Building ${APP_NAME} for macOS"
echo "──────────────────────────────────────────"

# 1. Clean previous artifacts
rm -rf build dist
echo "✓ Cleaned previous builds"

# 2. Generate platform icons from static/icon.png if missing
if [ ! -f "static/icon.icns" ]; then
    echo "→ Generating platform icons from static/icon.png..."
    python3 build_icon.py
fi

# 3. Run PyInstaller
echo "→ Running PyInstaller..."
pyinstaller peanut.spec --clean --noconfirm

if [ ! -d "dist/${APP_NAME}.app" ]; then
    echo "✗ Build failed — ${APP_NAME}.app not produced"
    exit 1
fi
echo "✓ Built dist/${APP_NAME}.app ($(du -sh "dist/${APP_NAME}.app" | cut -f1))"

# 4. Code signing (optional)
if [ -n "$DEVELOPER_ID" ]; then
    echo "→ Code-signing with: $DEVELOPER_ID"
    codesign --deep --force --verify --verbose \
        --sign "$DEVELOPER_ID" \
        --options runtime \
        "dist/${APP_NAME}.app"
    echo "✓ Code signed"
else
    echo "⚠ Skipping code-sign (set DEVELOPER_ID to enable)"
fi

# 5. Build DMG
echo "→ Creating DMG..."
rm -f "dist/${DMG_NAME}"

if command -v create-dmg &> /dev/null; then
    create-dmg \
        --volname "${APP_NAME}" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "${APP_NAME}.app" 175 190 \
        --hide-extension "${APP_NAME}.app" \
        --app-drop-link 425 190 \
        --no-internet-enable \
        "dist/${DMG_NAME}" \
        "dist/${APP_NAME}.app" || true
fi

# Fallback to hdiutil if create-dmg unavailable or failed
if [ ! -f "dist/${DMG_NAME}" ]; then
    echo "→ Using hdiutil fallback"
    hdiutil create -volname "${APP_NAME}" \
        -srcfolder "dist/${APP_NAME}.app" \
        -ov -format UDZO \
        "dist/${DMG_NAME}"
fi

echo "✓ Created dist/${DMG_NAME}"

# 6. Notarize (optional)
if [ -n "$APPLE_ID" ] && [ -n "$APPLE_TEAM_ID" ] && [ -n "$APPLE_PASSWORD" ]; then
    echo "→ Submitting for notarization..."
    xcrun notarytool submit "dist/${DMG_NAME}" \
        --apple-id "$APPLE_ID" \
        --team-id "$APPLE_TEAM_ID" \
        --password "$APPLE_PASSWORD" \
        --wait
    xcrun stapler staple "dist/${DMG_NAME}"
    echo "✓ Notarized + stapled"
else
    echo "⚠ Skipping notarization (set APPLE_ID, APPLE_TEAM_ID, APPLE_PASSWORD)"
fi

echo
echo "──────────────────────────────────────────"
echo " Build complete!"
echo "──────────────────────────────────────────"
echo " App: dist/${APP_NAME}.app"
echo " DMG: dist/${DMG_NAME} ($(du -sh "dist/${DMG_NAME}" | cut -f1))"
echo "──────────────────────────────────────────"
