"""
Peanut Server
=============
Flask server with Server-Sent Events for progressive scan results.
"""

import argparse
import json
import os
import queue
import sys
import threading
import webbrowser
from pathlib import Path

from flask import (Flask, Response, jsonify, render_template, request,
                   send_from_directory)

try:
    from send2trash import send2trash
    HAS_TRASH = True
except ImportError:
    HAS_TRASH = False

from scanner import PeanutScanner

app = Flask(__name__, template_folder="templates")

# ── State ─────────────────────────────────────────────────────────────────

scan_queue = queue.Queue()
scan_results = []
scan_stats = {}
scan_state = "idle"  # idle | scanning | complete | error
scan_error = ""
thumb_dir = ""
peanut_dir = ""

# ── Action log ────────────────────────────────────────────────────────────
# Persistent record of every meaningful action: deletes, moves, locks,
# unlocks, scans, errors. Lives at ~/.peanut/actions.log as NDJSON (one
# JSON object per line). Survives across sessions so you can answer
# "what did I delete last week?" Limited to the last ~10,000 entries to
# avoid unbounded growth.

import datetime as _dt
_log_lock = threading.Lock()  # writes from multiple endpoints, serialize

def _log_path():
    return os.path.join(peanut_dir, "actions.log") if peanut_dir else None

def log_action(level, action, message, **extra):
    """Append a structured entry to the action log.
    level   — 'info' | 'warn' | 'error' | 'success'
    action  — e.g. 'delete', 'move', 'lock', 'unlock', 'scan', 'error'
    message — human-readable text shown in the UI
    extra   — any extra fields (path, count, reason, etc.)
    """
    p = _log_path()
    if not p:
        return
    entry = {
        "ts": _dt.datetime.now().isoformat(timespec="seconds"),
        "level": level,
        "action": action,
        "message": message,
    }
    entry.update(extra)
    try:
        with _log_lock:
            with open(p, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        # Logging must never break the request that triggered it.
        pass


def read_log_tail(n=500):
    """Return the last n log entries as a list of dicts, newest first."""
    p = _log_path()
    if not p or not os.path.exists(p):
        return []
    try:
        with _log_lock:
            with open(p, "r", encoding="utf-8") as f:
                lines = f.readlines()
        out = []
        # Iterate the tail in reverse to get newest-first
        for line in reversed(lines[-n:]):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                # Skip malformed lines (e.g. partial write) without crashing
                continue
        return out
    except Exception:
        return []


def trim_log(max_lines=10000):
    """Keep the log file from growing unbounded by truncating to the last
    max_lines entries. Called opportunistically; doesn't need to be exact."""
    p = _log_path()
    if not p or not os.path.exists(p):
        return
    try:
        with _log_lock:
            with open(p, "r", encoding="utf-8") as f:
                lines = f.readlines()
        if len(lines) > max_lines * 1.1:  # 10% slack to avoid trimming every write
            with _log_lock:
                with open(p, "w", encoding="utf-8") as f:
                    f.writelines(lines[-max_lines:])
    except Exception:
        pass

# ── Pages ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    # Force the browser to re-fetch index.html every time. Without this,
    # users who download a new Peanut version often see the OLD UI because
    # their browser cached the previous index.html. Stale UI + new server
    # = bizarre bugs that are hard to diagnose.
    resp = app.make_response(render_template("index.html"))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

# ── SSE Stream ────────────────────────────────────────────────────────────

@app.route("/api/stream")
def stream():
    """Server-Sent Events endpoint for progressive scan results."""
    def generate():
        while True:
            try:
                msg = scan_queue.get(timeout=30)
                if msg is None:
                    break
                yield f"data: {json.dumps(msg)}\n\n"
                if msg.get("event") == "complete":
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'event': 'heartbeat'})}\n\n"
    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

# ── API ───────────────────────────────────────────────────────────────────

@app.route("/api/cancel-scan", methods=["POST"])
def api_cancel_scan():
    """Reset server-side scan state. The actual scan thread keeps running
    (Python threads can't be safely killed), but the UI stops listening
    and the user can start a new scan. Used as an escape hatch when the
    scanning view gets stuck."""
    global scan_results, scan_stats, scan_state, scan_error
    scan_state = "idle"
    scan_results = []
    scan_stats = {}
    scan_error = ""
    while not scan_queue.empty():
        try: scan_queue.get_nowait()
        except: break
    return jsonify({"ok": True})


@app.route("/api/scan", methods=["POST"])
def api_scan():
    global scan_results, scan_stats, scan_state, scan_error

    # Reject concurrent scans — only one scan at a time per server instance.
    # Without this, two simultaneous scans would race on shared globals
    # (scan_queue, scan_results, scan_stats) and produce garbled results.
    if scan_state == "scanning":
        return jsonify({
            "error": "A scan is already in progress. Wait for it to finish, "
                     "or restart Peanut to cancel.",
        }), 409

    data = request.json or {}
    paths = data.get("paths", [])
    recursive = data.get("recursive", True)
    file_types = data.get("file_types", [])  # e.g. ["images","videos","audio"]

    if not paths:
        return jsonify({"error": "No paths"}), 400

    valid = []
    for p in paths:
        exp = os.path.expanduser(p)
        if os.path.exists(exp):
            valid.append(exp)
        else:
            return jsonify({"error": f"Path not found: {p}"}), 400

    # Clear previous
    scan_results = []
    scan_stats = {}
    scan_state = "scanning"
    scan_error = ""
    while not scan_queue.empty():
        try: scan_queue.get_nowait()
        except: break

    log_action("info", "scan_started",
               f"Scan started: {len(valid)} folder{'' if len(valid)==1 else 's'}",
               paths=valid, recursive=recursive, file_types=file_types)

    def run():
        global scan_results, scan_stats, scan_state, scan_error
        try:
            scanner = PeanutScanner(
                paths=valid, recursive=recursive,
                thumb_dir=thumb_dir, cache_dir=peanut_dir,
                file_types=file_types,
            )
            for event in scanner.scan_progressive():
                scan_queue.put(event)
                if event["event"] == "group":
                    scan_results.append(event["data"])
                elif event["event"] == "complete":
                    scan_stats = event["data"].get("stats", {})
            scan_state = "complete"
            log_action("success", "scan_complete",
                       f"Scan complete: {len(scan_results)} duplicate group{'' if len(scan_results)==1 else 's'} found",
                       groups=len(scan_results),
                       recoverable_bytes=scan_stats.get("recoverable_bytes", 0))
        except Exception as e:
            scan_error = str(e)
            scan_state = "error"
            scan_queue.put({"event": "error", "data": {"message": str(e)}})
            log_action("error", "scan_failed",
                       f"Scan failed: {e}", reason=str(e))

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"status": "started"})


@app.route("/api/results")
def api_results():
    return jsonify({
        "groups": scan_results,
        "stats": scan_stats,
        "state": scan_state,
        "error": scan_error if scan_state == "error" else "",
    })


@app.route("/api/browse")
def api_browse():
    req_path = request.args.get("path", "")

    if not req_path:
        home = os.path.expanduser("~")
        roots = [{"name": "Home", "path": home, "icon": "home"}]
        for name, icon in [("Desktop","desktop"),("Documents","file"),("Downloads","download"),
                           ("Pictures","image"),("Movies","film"),("Photos","image"),
                           ("Music","music")]:
            fp = os.path.join(home, name)
            if os.path.isdir(fp):
                roots.append({"name": name, "path": fp, "icon": icon})

        if os.path.isdir("/Volumes"):
            try:
                for v in sorted(os.listdir("/Volumes")):
                    vp = os.path.join("/Volumes", v)
                    if os.path.isdir(vp) and not v.startswith("."):
                        roots.append({"name": v, "path": vp, "icon": "drive"})
            except PermissionError:
                pass

        if sys.platform == "win32":
            import string
            for L in string.ascii_uppercase:
                d = f"{L}:\\"
                if os.path.exists(d):
                    roots.append({"name": d, "path": d, "icon": "drive"})

        for mr in ["/media", "/mnt"]:
            if os.path.isdir(mr):
                try:
                    for d in sorted(os.listdir(mr)):
                        dp = os.path.join(mr, d)
                        if os.path.isdir(dp):
                            roots.append({"name": d, "path": dp, "icon": "drive"})
                except PermissionError:
                    pass

        return jsonify({"current": "", "parent": "", "dirs": roots, "is_root": True})

    expanded = os.path.expanduser(req_path)
    if not os.path.isdir(expanded):
        return jsonify({"error": "Not a directory"}), 400

    abs_path = os.path.abspath(expanded)
    parent = os.path.dirname(abs_path)

    dirs = []
    try:
        for entry in sorted(os.listdir(abs_path)):
            if entry.startswith("."):
                continue
            full = os.path.join(abs_path, entry)
            if os.path.isdir(full):
                mc = 0
                try:
                    for fn in os.listdir(full):
                        ext = os.path.splitext(fn)[1].lower()
                        if ext in {".jpg",".jpeg",".png",".gif",".mp4",".mov",".mkv",
                                   ".avi",".webp",".heic",".bmp",".tiff",".webm"}:
                            mc += 1
                except PermissionError:
                    pass
                dirs.append({"name": entry, "path": full, "media_count": mc, "icon": "folder"})
    except PermissionError:
        return jsonify({"error": "Permission denied"}), 403

    return jsonify({
        "current": abs_path,
        "parent": parent if parent != abs_path else "",
        "dirs": dirs, "is_root": False,
    })


@app.route("/api/delete", methods=["POST"])
def api_delete():
    global scan_results
    data = request.json or {}
    file_paths = data.get("files", [])
    mode = data.get("mode", "trash")
    move_to = data.get("move_to", "")

    if not file_paths:
        return jsonify({"error": "No files"}), 400

    # Final safety net: filter out anything the user has locked. The UI
    # already excludes locked files from its selection, but a malformed
    # client request (or a stale browser tab) could still target one. We
    # never delete a locked file no matter what the request says.
    locked = _get_lock_cache().list_locked()
    blocked = [p for p in file_paths if p in locked]
    file_paths = [p for p in file_paths if p not in locked]

    results = {"deleted": [], "moved": [], "errors": [],
               "blocked_locked": blocked}

    # Log every blocked attempt — useful for the audit trail. Done up
    # front so the early-return-when-everything-blocked path still records.
    for bp in blocked:
        log_action("warn", "delete_blocked",
                   f"Delete blocked by lock: {os.path.basename(bp)}",
                   path=bp, reason="file is locked")

    if not file_paths:
        # Everything was locked — nothing to do, but don't error
        return jsonify(results)

    for fp in file_paths:
        try:
            if not os.path.exists(fp):
                results["errors"].append({"path": fp, "error": "Not found"})
                continue

            if move_to:
                os.makedirs(move_to, exist_ok=True)
                dest = os.path.join(move_to, os.path.basename(fp))
                # Handle name collision
                if os.path.exists(dest):
                    base, ext = os.path.splitext(os.path.basename(fp))
                    i = 1
                    while os.path.exists(dest):
                        dest = os.path.join(move_to, f"{base}_{i}{ext}")
                        i += 1
                import shutil
                shutil.move(fp, dest)
                results["moved"].append(fp)
                log_action("success", "move",
                           f"Moved: {os.path.basename(fp)}",
                           path=fp, new_path=dest)
            elif mode == "trash" and HAS_TRASH:
                send2trash(fp)
                results["deleted"].append(fp)
                log_action("success", "trash",
                           f"Trashed: {os.path.basename(fp)}",
                           path=fp, recoverable=True)
            else:
                os.remove(fp)
                results["deleted"].append(fp)
                log_action("success", "delete_permanent",
                           f"Permanently deleted: {os.path.basename(fp)}",
                           path=fp, recoverable=False)
        except Exception as e:
            results["errors"].append({"path": fp, "error": str(e)})
            log_action("error", "delete_failed",
                       f"Failed to delete {os.path.basename(fp)}: {e}",
                       path=fp, reason=str(e))

    # Trim the log opportunistically (cheap when small, no-op when fine)
    trim_log()

    # Update results
    removed = set(results["deleted"]) | set(results["moved"])
    updated = []
    for g in scan_results:
        g["files"] = [f for f in g["files"] if f["path"] not in removed]
        if len(g["files"]) >= 2:
            updated.append(g)
    scan_results = updated

    return jsonify(results)


# ── Locks ─────────────────────────────────────────────────────────────────
# Files the user has marked as "protected from deletion." Persisted in the
# scanner's cache.db so locks survive across runs and re-scans.

_lock_cache = None
def _get_lock_cache():
    """Lazy singleton — peanut_dir gets set in main() at startup."""
    global _lock_cache
    if _lock_cache is None:
        from scanner import HashCache
        _lock_cache = HashCache(os.path.join(peanut_dir, "cache.db"))
    return _lock_cache


@app.route("/api/locks", methods=["GET"])
def api_locks_list():
    """Return all locked paths so the client can hydrate its state."""
    return jsonify({"locked": sorted(_get_lock_cache().list_locked())})


@app.route("/api/locks/toggle", methods=["POST"])
def api_locks_toggle():
    """Bulk lock or unlock files. Body: {"paths":[...], "lock":bool}.
    Idempotent — locking already-locked files (or unlocking unlocked
    ones) is a no-op."""
    data = request.json or {}
    paths = data.get("paths", [])
    lock_it = bool(data.get("lock", True))
    if not isinstance(paths, list):
        return jsonify({"error": "paths must be a list"}), 400

    cache = _get_lock_cache()
    if lock_it:
        for p in paths:
            cache.lock(p)
            log_action("info", "lock",
                       f"Locked: {os.path.basename(p)}", path=p)
    else:
        for p in paths:
            cache.unlock(p)
            log_action("info", "unlock",
                       f"Unlocked: {os.path.basename(p)}", path=p)
    return jsonify({"ok": True, "locked": sorted(cache.list_locked())})


# ── Action log endpoints ──────────────────────────────────────────────────

@app.route("/api/log", methods=["GET"])
def api_log_get():
    """Return the most recent log entries (newest first)."""
    n = int(request.args.get("n", 500))
    return jsonify({"entries": read_log_tail(n)})


@app.route("/api/log/clear", methods=["POST"])
def api_log_clear():
    """Clear the log. Body: {"hard": true|false}.
    Soft clear (default) keeps the file but signals the client to clear
    its in-memory view. Hard clear deletes the file too."""
    data = request.json or {}
    hard = bool(data.get("hard", False))
    p = _log_path()
    if hard and p and os.path.exists(p):
        try:
            with _log_lock:
                os.remove(p)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    log_action("info", "log_clear",
               f"Action log cleared ({'hard' if hard else 'soft'})")
    return jsonify({"ok": True, "hard": hard})


@app.route("/api/move-one", methods=["POST"])
def api_move_one():
    """Move a single file to a new folder. If the file was locked, the
    lock follows it to the new path so the user's protection isn't
    silently lost."""
    global scan_results
    data = request.json or {}
    source = data.get("source", "")
    dest_folder = data.get("dest_folder", "")

    if not source or not os.path.exists(source):
        return jsonify({"error": "Source not found"}), 400

    dest_folder = os.path.expanduser(dest_folder)
    if not os.path.isdir(dest_folder):
        return jsonify({"error": "Destination folder not found"}), 400

    try:
        import shutil
        dest = os.path.join(dest_folder, os.path.basename(source))
        # Handle name collision
        if os.path.exists(dest):
            base, ext = os.path.splitext(os.path.basename(source))
            i = 1
            while os.path.exists(dest):
                dest = os.path.join(dest_folder, f"{base}_{i}{ext}")
                i += 1

        # Transfer lock BEFORE the file move. If the file was locked, we
        # unlock the old path and lock the new one. Doing this before the
        # actual move means a crash mid-transfer can't leave a phantom
        # lock on a non-existent path.
        cache = _get_lock_cache()
        was_locked = cache.is_locked(source)
        if was_locked:
            cache.unlock(source)
            cache.lock(dest)

        shutil.move(source, dest)

        # Update scan_results with new path
        for g in scan_results:
            for f in g.get("files", []):
                if f.get("path") == source:
                    f["path"] = dest
                    f["dir"] = os.path.dirname(dest)
                    f["name"] = os.path.basename(dest)

        log_action("success", "move",
                   f"Moved: {os.path.basename(source)} → {dest_folder}",
                   path=source, new_path=dest, lock_transferred=was_locked)
        return jsonify({"ok": True, "new_path": dest, "lock_transferred": was_locked})
    except Exception as e:
        log_action("error", "move_failed",
                   f"Failed to move {os.path.basename(source)}: {e}",
                   path=source, reason=str(e))
        return jsonify({"error": str(e)}), 500


@app.route("/api/open-folder", methods=["POST"])
def api_open_folder():
    data = request.json or {}
    fp = data.get("path", "")
    if not fp or not os.path.exists(fp):
        return jsonify({"error": "Not found"}), 404
    try:
        import subprocess as sp
        if sys.platform == "darwin":
            sp.Popen(["open", "-R", fp], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        elif sys.platform == "win32":
            sp.Popen(["explorer", "/select,", fp], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        else:
            sp.Popen(["xdg-open", os.path.dirname(fp)], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/thumb/<path:filename>")
def serve_thumb(filename):
    return send_from_directory(thumb_dir, filename)


@app.route("/original")
def serve_original():
    fp = request.args.get("path", "")
    if not fp or not os.path.exists(fp):
        return "Not found", 404
    return send_from_directory(os.path.dirname(fp), os.path.basename(fp))


def show_credits():
    """Print the easter-egg credits screen and exit."""
    peanut_art = r"""
                          ____
                       ,o88888
                    ,o8888888'
              ,:o:o:oooo. ,8O88Pd'
          ,.::.::o:ooooOoOoO. ,oO8O8Pd'
        ,.:.::o:ooOoOoOO8O8OOo.8OOPd'
       ,..:.::o:ooOoOO8O88O8O.O8Pd'
      ,o:.::o:ooOoOoOO8O8OO8O8Pd'
     ,.:.:o:oooOoOO8O88O8O8Pd'
   ` -.:.::o:ooOoOoOO8O8OOd'
       `-.::.::ooOoOoO8O8d'
          `-.:o:ooOoO8O'
              `-.::oO'
                 `'
"""
    print(peanut_art)
    print("  Peanut · content-aware duplicate finder")
    print("  ──────────────────────────────────────────")
    print("  built by cody browne")
    print()
    print("  github     github.com/cbrwe")
    print("  ig         @codybrowne")
    print("  email      cbrwe@proton.me")
    print("  text       (808) 301-3339")
    print()
    print("  peanut is my dog's name, fyi. and i love peanut.")
    print()


# ── CLI ───────────────────────────────────────────────────────────────────

def main():
    global thumb_dir, peanut_dir

    parser = argparse.ArgumentParser(description="Peanut - Find duplicate images & videos")
    parser.add_argument("paths", nargs="*", default=[])
    parser.add_argument("--port", "-p", type=int, default=8787)
    parser.add_argument("--no-recursive", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--threshold-image", type=int, default=10)
    parser.add_argument("--threshold-video", type=int, default=12)
    parser.add_argument("--credits", action="store_true",
                        help="Show credits and exit")
    args = parser.parse_args()

    if args.credits:
        show_credits()
        sys.exit(0)

    import scanner as sc
    sc.IMAGE_THRESHOLD = args.threshold_image
    sc.VIDEO_THRESHOLD = args.threshold_video

    peanut_dir = os.path.join(os.path.expanduser("~"), ".peanut")
    os.makedirs(peanut_dir, exist_ok=True)
    thumb_dir = os.path.join(peanut_dir, "thumbnails")
    os.makedirs(thumb_dir, exist_ok=True)

    if args.paths:
        for p in args.paths:
            if not os.path.exists(os.path.expanduser(p)):
                print(f"Error: {p} does not exist")
                sys.exit(1)

        print(f"\n  Peanut")
        print(f"  Scanning: {', '.join(args.paths)}")
        print(f"  UI: http://localhost:{args.port}\n")

        def auto_scan():
            global scan_results, scan_stats, scan_state
            import time; time.sleep(1.5)
            scan_state = "scanning"
            try:
                s = PeanutScanner(
                    paths=[os.path.expanduser(p) for p in args.paths],
                    recursive=not args.no_recursive,
                    thumb_dir=thumb_dir, cache_dir=peanut_dir,
                )
                for event in s.scan_progressive():
                    scan_queue.put(event)
                    if event["event"] == "group":
                        scan_results.append(event["data"])
                    elif event["event"] == "complete":
                        scan_stats = event["data"].get("stats", {})
                scan_state = "complete"
            except Exception as e:
                scan_state = "error"
                scan_queue.put({"event": "error", "data": {"message": str(e)}})

        threading.Thread(target=auto_scan, daemon=True).start()
    else:
        print(f"\n  Peanut")
        print(f"  UI: http://localhost:{args.port}\n")

    if not args.no_browser:
        threading.Timer(2.0, lambda: webbrowser.open(f"http://localhost:{args.port}")).start()

    app.run(host="127.0.0.1", port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()


# ──────────────────────────────────────────────────────────────────────────
#                    For whoever made it to the bottom.
# ──────────────────────────────────────────────────────────────────────────
#
# The thing that's going to change your life is not a habit, a morning
# routine, or a better system. It's one decision made from the part of
# you that is done waiting for conditions to be perfect. One ugly,
# half-ready, terrifying move made before you feel ready to make it.
#
# You think I was ready to ship my app? I wasn't. I spent months building
# that thing, and every single night before bed I'd tell myself "tomorrow's
# the day." I could not wait to lock in and finally ship it. And then
# tomorrow would come, and I would find a reason not to.
#
# Everything you admire about someone else's life started with them just
# doing the thing before they were ready. And that moment looked nothing
# like a beginning. It looked like a bad idea. It looked like the wrong
# time. It looked like something they'd probably regret.
#
# They did it anyway. That's the whole story.
#
#                                                          — cody browne
# ──────────────────────────────────────────────────────────────────────────
