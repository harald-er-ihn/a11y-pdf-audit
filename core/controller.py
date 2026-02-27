"""
Controller zur Steuerung von Hintergrundprozessen.
"""

import os
import shutil
import threading
import time

import requests

from core.facade import AuditFacade
from core.utils.config_loader import load_config
from core.utils.error_utils import log_error, log_info


def start_audit_background(url, max_pages, depth, force_ai=False):
    """Startet den Prozess in einem Thread (jetzt mit force_ai)."""
    thread = threading.Thread(target=_run_job, args=(url, max_pages, depth, force_ai))
    thread.daemon = True
    thread.start()


def _keep_alive_worker(stop_event):
    """Pingt die App öffentlich an, damit Fly.io sie nicht abschaltet."""
    app_name = os.environ.get("FLY_APP_NAME")
    if not app_name:
        return
    target_url = f"https://{app_name}.fly.dev/"
    log_info(f"[Keep-Alive] Gestartet. Pinge {target_url}")

    while not stop_event.is_set():
        try:
            requests.get(target_url, timeout=10)
        except Exception:
            pass
        if stop_event.wait(timeout=20):
            break


def _cleanup_old_reports(output_dir, days=14):
    """Löscht alte Berichte (> 14 Tage)."""
    now = time.time()
    cutoff = now - (days * 86400)
    if not os.path.exists(output_dir):
        return
    for root, _, files in os.walk(output_dir):
        for file in files:
            if file == "audit.log":
                continue
            fpath = os.path.join(root, file)
            try:
                if os.path.isfile(fpath) and os.stat(fpath).st_mtime < cutoff:
                    os.remove(fpath)
            except OSError as err:
                log_error(f"Fehler beim Löschen von {fpath}: {err}")
                pass


def _run_job(url, max_pages, depth, force_ai=False):
    """Worker Funktion, die den Audit durchführt."""
    stop_event = threading.Event()
    keep_alive_thread = threading.Thread(target=_keep_alive_worker, args=(stop_event,))
    keep_alive_thread.daemon = True
    keep_alive_thread.start()

    try:
        cfg = load_config()
        output_root = cfg["active_paths"]["output"]
        _cleanup_old_reports(output_root)

        log_info(f"Job gestartet: {url} (AI: {force_ai})")

        facade = AuditFacade()
        # Hier wird force_ai an die Facade übergeben
        result_path = facade.run_full_audit(url, max_pages, depth, force_ai=force_ai)

        if result_path and os.path.exists(result_path):
            filename = os.path.basename(result_path)
            dest_path = os.path.join(output_root, filename)
            if not os.path.exists(dest_path):
                shutil.copy2(result_path, dest_path)

    except Exception as err:
        log_error(f"Job Fehler: {err}")
    finally:
        stop_event.set()
        keep_alive_thread.join(timeout=2)
        log_info("Prozess fertig.")
