# Building Peanut

Cross-platform build instructions for shipping Peanut as a real installable app on macOS, Windows, and Linux.

## TL;DR

```bash
pip install -r requirements.txt
pip install -r requirements-build.txt

bash build_mac.sh         # macOS  → dist/Peanut.app + Peanut-1.0.0.dmg
build_windows.bat         # Windows → dist/Peanut/  (+ installer.exe if Inno Setup is installed)
bash build_linux.sh       # Linux  → dist/Peanut/ + tarball (+ AppImage if appimagetool is on PATH)
```

For automated cross-platform builds, push a version tag and let GitHub Actions do all three:

```bash
git tag v1.0.0
git push origin v1.0.0
```

This triggers `.github/workflows/build.yml` which produces a draft GitHub Release with all artifacts attached.

## Prerequisites

### All platforms
- Python 3.9+
- Runtime dependencies: `pip install -r requirements.txt`
- Build dependencies: `pip install -r requirements-build.txt`
- `static/icon.png` — 1024×1024 master icon (already included)

### macOS
- macOS 11 (Big Sur) or later
- Xcode Command Line Tools: `xcode-select --install`
- Optional: `brew install create-dmg` for prettier DMGs (falls back to `hdiutil`)
- Optional: Apple Developer ID for code signing (avoids Gatekeeper warnings)

### Windows
- Windows 10 or later
- Optional: Inno Setup 6 from https://jrsoftware.org/isinfo.php to build the `.exe` installer
- Optional: code signing certificate from DigiCert/Sectigo/SSL.com to avoid SmartScreen warnings

### Linux
- Ubuntu 20.04+ or equivalent
- For AppImage builds: `appimagetool` from https://github.com/AppImage/AppImageKit/releases
- `libfuse2` (required to run AppImage on the build host)

## Code signing

### macOS

Without signing, users see a "Peanut.app cannot be opened because it is from an unidentified developer" dialog and must right-click → Open the first time. To distribute cleanly:

```bash
export DEVELOPER_ID="Developer ID Application: Your Name (TEAMID)"
bash build_mac.sh
```

For full notarization (required for distribution outside the App Store):

```bash
export DEVELOPER_ID="Developer ID Application: Your Name (TEAMID)"
export APPLE_ID="your.apple.id@example.com"
export APPLE_TEAM_ID="ABCDE12345"
export APPLE_PASSWORD="xxxx-xxxx-xxxx-xxxx"   # app-specific password
bash build_mac.sh
```

App-specific passwords: appleid.apple.com → Sign-In & Security → App-Specific Passwords.

### Windows

Without signing, users see a Windows SmartScreen warning ("Windows protected your PC"). To avoid:

1. Buy a code signing certificate (~$200–400/year)
2. Sign the executable before packaging:

```cmd
signtool sign /a /tr http://timestamp.digicert.com /td sha256 /fd sha256 dist\Peanut\Peanut.exe
build_windows.bat
```

## Output structure

```
dist/
├── Peanut.app                           # macOS app bundle
├── Peanut-1.0.0.dmg                     # macOS installer
├── Peanut/                              # Windows / Linux folder
│   ├── Peanut.exe (or Peanut on Linux)
│   └── _internal/                       # Bundled libraries
├── Peanut-1.0.0-windows-installer.exe   # Windows installer (if Inno Setup ran)
├── Peanut-1.0.0-x86_64.AppImage         # Linux AppImage (if appimagetool ran)
└── Peanut-1.0.0-linux-x86_64.tar.gz     # Linux tarball
```

## CI / CD

`.github/workflows/build.yml` builds on macOS, Windows, and Ubuntu runners simultaneously when you push a `v*` tag. To run a build manually without tagging, use the "Actions" tab → "Build and Release" → "Run workflow" on GitHub.

For signed CI builds, add these GitHub Secrets to your repo (`Settings → Secrets and variables → Actions`):

**macOS:**
- `APPLE_DEVELOPER_ID_BASE64` — base64-encoded `.p12` certificate
- `APPLE_DEVELOPER_ID_PASSWORD`
- `APPLE_ID`
- `APPLE_TEAM_ID`
- `APPLE_APP_PASSWORD`

**Windows:**
- `WINDOWS_CERT_BASE64` — base64-encoded `.pfx` certificate
- `WINDOWS_CERT_PASSWORD`

(The current workflow doesn't pull these in — wire them up if you need signed CI builds.)

## Bundling ffmpeg

ffmpeg isn't bundled because it's large and license-sensitive. Image dedup works without it; video and audio dedup degrade gracefully if ffmpeg isn't on the user's PATH.

If you want to bundle it:

1. Download static builds:
   - macOS: https://evermeet.cx/ffmpeg/
   - Windows: https://www.gyan.dev/ffmpeg/builds/
   - Linux: https://johnvansickle.com/ffmpeg/

2. Place binaries in `static/bin/ffmpeg` (and `ffprobe`).

3. Add to `peanut.spec` `binaries`:

   ```python
   binaries = [
       ("static/bin/ffmpeg", "."),
       ("static/bin/ffprobe", "."),
   ]
   ```

4. Update `scanner.py` to look for the bundled binary first (via `sys._MEIPASS`), then fall back to system `PATH`.

## Troubleshooting

**PyInstaller misses a module at runtime:**
Add it to `hiddenimports` in `peanut.spec`.

**App is huge (~200MB+):**
That's normal for PyInstaller bundles — Python + Pillow + numpy + Flask alone is ~80MB compressed. To shrink:
- Add `upx=True` in the spec (downloads UPX automatically)
- Trim unused libraries via the `excludes` list

**"Python.framework not found" on Mac:**
Use a Python from python.org rather than the system `/usr/bin/python3` or Homebrew shim.

**"Damaged" warning when opening Peanut.app:**
That's macOS Gatekeeper. Either right-click → Open the first time, or sign + notarize as described above. For your own use, you can also strip the quarantine attribute: `xattr -cr Peanut.app`.

**HEIC files don't get thumbnails:**
The bundle ships with `pillow-heif` for HEIC support. If thumbnails still don't appear, ffmpeg as a fallback handles HEIC if installed on the user's PATH.

## Files in this build system

```
build_icon.py              # Generates .icns / .ico / favicon from icon.png
build_linux.sh             # Linux build script
build_mac.sh               # macOS build script
build_windows.bat          # Windows build script
installer.iss              # Inno Setup script (Windows installer)
peanut_desktop.py          # Native-app entry point — Flask + pywebview wrapper
launcher.py                # Legacy entry point — Flask + system browser (kept as fallback)
peanut.spec                # PyInstaller recipe (all 3 platforms)
requirements-build.txt     # Build-time dependencies (pyinstaller)
.github/workflows/build.yml # GitHub Actions CI for cross-platform release builds
```

## Why pywebview?

The bundled app uses `pywebview` (a thin Python ↔ native webview bridge) instead of opening Safari/Chrome. Three reasons:

1. **Real native window.** No browser tab, no URL bar, no bookmarks bar — looks and behaves like a real desktop app.
2. **Real drag-and-drop.** Browsers deliberately strip the filesystem path from drag events for security. pywebview's webview keeps the path, so dragging a folder from Finder/Explorer/Files actually works.
3. **Cleaner quit behavior.** Closing the window quits the app; the Flask server is a daemon thread that dies with the main process.

If pywebview isn't installed (e.g. running from a fresh source checkout), `peanut_desktop.py` falls back to opening the system browser — same behavior as `launcher.py`.

## Running from source vs. from bundle

```bash
python app.py             # Source dev mode — opens system browser, fastest iteration
python peanut_desktop.py  # Source dev mode — uses pywebview if installed, browser fallback otherwise
./Peanut.app              # Bundled app — pywebview required, baked in
```

The frontend detects which environment it's in (`window.pywebview` is defined inside the native app) and adjusts the dropzone hint accordingly.

