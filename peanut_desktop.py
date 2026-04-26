"""
Peanut Desktop Entry Point
==========================
Native desktop app wrapper using pywebview. Replaces the browser-based
launcher for the bundled .app/.exe distribution.

Why pywebview instead of just opening the browser?
  - Real native window (no browser tab, no URL bar, no bookmarks bar)
  - Real OS-level drag-and-drop with full filesystem paths (browsers
    deliberately strip paths from drag events for security)
  - Cleaner quit behavior (close the window, app exits)
  - Looks and feels like a real Mac/Windows/Linux app

Architecture:
  1. Start Flask in a background thread on a random free port
  2. Wait briefly for the server to become reachable
  3. Open a pywebview window pointing at http://127.0.0.1:PORT
  4. Register a Python-side drop handler that captures real filesystem
     paths from native drag-and-drop and pushes them back into JS via
     window.evaluate_js so the existing addPath() flow can handle them
  5. When the user closes the window, the app exits (server thread is
     daemon, so it dies with the main thread)

When you run `python app.py` from source you bypass this entirely —
the browser-based flow still works for development. This file is only
invoked from the bundled app.
"""

import json
import logging
import os
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

# pywebview is imported lazily inside main() so this file can at least
# parse on systems without it (useful for the source-tree test runners).


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


def wait_for_server(url: str, timeout: float = 8.0) -> bool:
    """Poll the server until it responds or we hit the timeout. Returns
    True if the server is reachable, False on timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.5) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.1)
    return False


def _on_window_loaded(window):
    """Wire up the native drop handler once the page has rendered.

    pywebview's drop event fires Python-side with a list of (filename,
    full_path) tuples. We extract the real paths and shove them into JS
    via evaluate_js so the existing addPath() flow handles them — same
    code path as typed-in or browser-picked paths.
    """
    def on_drop(event):
        try:
            files = event.get("dataTransfer", {}).get("files", []) or []
            paths = [f.get("pywebviewFullPath") or f.get("path") or "" for f in files]
            paths = [p for p in paths if p]
            if not paths:
                return
            # Push to JS — the frontend's addDroppedPaths() handles
            # validation, dedup, and the chip UI for us.
            payload = json.dumps(paths)
            window.evaluate_js(f"window.addDroppedPaths && window.addDroppedPaths({payload})")
        except Exception as e:
            print(f"Drop handler error: {e}", file=sys.stderr)

    try:
        # Attach the drop handler to the document body. This is what
        # signals pywebview-cocoa to capture real paths instead of
        # passing-through the browser-stripped event.
        window.dom.document.events.drop += on_drop
    except Exception as e:
        print(f"Could not attach drop handler: {e}", file=sys.stderr)


class JSBridge:
    """Methods exposed to JavaScript via window.pywebview.api.

    Call from JS as: pywebview.api.is_native()
    The frontend uses is_native() to detect the desktop environment and
    adapt its UI (better dropzone hint, etc.).
    """

    def is_native(self):
        return {"native": True, "platform": sys.platform}


def main() -> None:
    # 1. Configure data directory before importing app
    app_data = get_app_data_dir()
    os.environ["PEANUT_DATA_DIR"] = app_data

    # Silence Werkzeug's request log so the app's stderr stays quiet.
    # (Errors still propagate normally.)
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    # 2. Pick a port and import the Flask app
    port = find_open_port()
    url = f"http://127.0.0.1:{port}"

    from app import app
    import app as app_module

    # Override paths so the bundled app writes to the per-user data dir
    app_module.peanut_dir = app_data
    app_module.thumb_dir = os.path.join(app_data, "thumbnails")
    os.makedirs(app_module.thumb_dir, exist_ok=True)

    # 3. Start Flask in a background daemon thread
    def run_server():
        try:
            app.run(host="127.0.0.1", port=port, debug=False,
                    threaded=True, use_reloader=False)
        except Exception as e:
            print(f"Flask server error: {e}", file=sys.stderr)

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # 4. Wait for the server to actually accept connections
    if not wait_for_server(url, timeout=10.0):
        print(f"Server failed to start on {url}", file=sys.stderr)
        sys.exit(1)

    # 5. Open the native window
    try:
        import webview
    except ImportError:
        # Graceful fallback: no pywebview → open in browser instead.
        # Useful for source dev when pywebview isn't installed.
        import webbrowser
        print("pywebview not available, falling back to browser", file=sys.stderr)
        webbrowser.open(url)
        try:
            server_thread.join()
        except KeyboardInterrupt:
            sys.exit(0)
        return

    bridge = JSBridge()
    window = webview.create_window(
        title="Peanut",
        url=url,
        width=1280,
        height=820,
        min_size=(900, 600),
        resizable=True,
        fullscreen=False,
        confirm_close=False,
        text_select=True,
        js_api=bridge,
    )

    # Register the drop handler once the page is loaded. Attaching too
    # early would fail because window.dom isn't ready yet.
    window.events.loaded += lambda: _on_window_loaded(window)

    # webview.start() blocks until the window closes. confirm_close=False
    # means closing the window quits immediately. When this returns,
    # server_thread (daemon) dies with the main thread.
    # Force a clean exit when the user clicks the close button.
    # Works around a macOS Tahoe + pywebview 6.2 quirk where the first
    # close click only "pulses" the window instead of fully quitting.
    # os._exit() bypasses any pywebview/macOS reload logic.
    window.events.closing += lambda: os._exit(0)

    webview.start(debug=False)


if __name__ == "__main__":
    main()


