"""
Peanut Launcher
===============
Entry point used by the standalone (PyInstaller-built) app. Picks an
available port, sets up a per-platform writable data directory, opens
the user's browser, and runs the Flask server.

When you run `python app.py` from source you bypass this — `app.py`
has its own __main__ block. This file is only invoked from the bundled
app where there's no terminal.
"""

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


def find_open_port(start: int = 8787, end: int = 8800) -> int:
    """Return the first available TCP port in [start, end), else `start`."""
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start


def get_app_data_dir() -> str:
    """Cross-platform writable directory for cache + thumbnails.

    macOS:   ~/Library/Application Support/Peanut
    Windows: %APPDATA%/Peanut
    Linux:   ~/.local/share/peanut
    """
    home = Path.home()
    if sys.platform == "darwin":
        d = home / "Library" / "Application Support" / "Peanut"
    elif sys.platform == "win32":
        d = Path(os.environ.get("APPDATA", str(home))) / "Peanut"
    else:
        d = home / ".local" / "share" / "peanut"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


def main() -> None:
    # Configure data directory before importing app so paths get picked up
    app_data = get_app_data_dir()
    os.environ["PEANUT_DATA_DIR"] = app_data

    port = find_open_port()
    url = f"http://127.0.0.1:{port}"

    # Lazy import — env vars must be set first
    from app import app
    import app as app_module

    # Override paths so the bundled app writes to the per-user data dir,
    # not a hidden ~/.peanut folder. Keeps Mac/Windows behavior native.
    app_module.peanut_dir = app_data
    app_module.thumb_dir = os.path.join(app_data, "thumbnails")
    os.makedirs(app_module.thumb_dir, exist_ok=True)

    # Open browser shortly after Flask boots
    def open_browser() -> None:
        time.sleep(1.5)
        webbrowser.open(url)

    threading.Thread(target=open_browser, daemon=True).start()

    print(f"Peanut starting on {url}")
    print(f"Data directory: {app_data}")

    try:
        app.run(host="127.0.0.1", port=port, debug=False,
                threaded=True, use_reloader=False)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
