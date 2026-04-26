"""
Build platform icons from static/icon.png.

Generates:
  static/icon.icns   — macOS app icon (multi-resolution iconset)
  static/icon.ico    — Windows app icon
  static/favicon.png — Web favicon (32x32)

Source:
  static/icon.png    — A 1024x1024 PNG with the master icon.

Run:
  python3 build_icon.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "static" / "icon.png"


def ensure_source() -> Image.Image:
    if not SRC.exists():
        sys.exit(f"✗ {SRC} not found. Place a 1024x1024 PNG there first.")
    img = Image.open(SRC).convert("RGBA")
    if img.size != (1024, 1024):
        # Don't fail — just resize. Warn so the user knows.
        print(f"⚠ {SRC} is {img.size}, resizing to 1024x1024.")
        img = img.resize((1024, 1024), Image.LANCZOS)
    return img


def make_favicon(master: Image.Image) -> None:
    out = ROOT / "static" / "favicon.png"
    fav = master.resize((32, 32), Image.LANCZOS)
    fav.save(out, "PNG")
    print(f"✓ {out}")


def make_ico(master: Image.Image) -> None:
    out = ROOT / "static" / "icon.ico"
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    master.save(out, format="ICO", sizes=sizes)
    print(f"✓ {out}")


def make_icns(master: Image.Image) -> None:
    """Build a macOS .icns. Uses `iconutil` if available (Mac only), else
    falls back to PIL's basic ICNS support."""
    out = ROOT / "static" / "icon.icns"
    if sys.platform == "darwin" and shutil.which("iconutil"):
        with tempfile.TemporaryDirectory() as tmp:
            iconset = Path(tmp) / "icon.iconset"
            iconset.mkdir()
            # Apple's required iconset filenames + sizes
            specs = [
                (16, "icon_16x16.png"),
                (32, "icon_16x16@2x.png"),
                (32, "icon_32x32.png"),
                (64, "icon_32x32@2x.png"),
                (128, "icon_128x128.png"),
                (256, "icon_128x128@2x.png"),
                (256, "icon_256x256.png"),
                (512, "icon_256x256@2x.png"),
                (512, "icon_512x512.png"),
                (1024, "icon_512x512@2x.png"),
            ]
            for px, name in specs:
                master.resize((px, px), Image.LANCZOS).save(iconset / name, "PNG")
            subprocess.check_call([
                "iconutil", "-c", "icns", str(iconset), "-o", str(out)
            ])
        print(f"✓ {out} (via iconutil)")
    else:
        # Cross-platform fallback. PIL writes a valid (if minimal) .icns.
        try:
            master.save(out, format="ICNS")
            print(f"✓ {out} (via Pillow)")
        except Exception as e:
            print(f"⚠ Could not generate {out}: {e}")
            print(f"  (Build on macOS with `iconutil` for best results.)")


def main() -> None:
    print("Generating platform icons from", SRC)
    master = ensure_source()
    make_favicon(master)
    make_ico(master)
    make_icns(master)
    print("Done.")


if __name__ == "__main__":
    main()
