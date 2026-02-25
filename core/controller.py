"""
Controller zur Steuerung von Hintergrundprozessen.
Enthält Keep-Alive Logik (Public Ping) und Dateiverwaltung (Auto-Cleanup).
"""

import os
import shutil
import threading
import time

import requests

from core.facade import AuditFacade
from core.utils.config_loader import load_config
from core.utils.error_utils import log_error, log_info


def start_audit_background(url, max_pages, depth):
    """Startet den Prozess in einem Thread."""
    thread = threading.Thread(target=_run_job, args=(url, max_pages, depth))
    thread.daemon = True
    thread.start()


def _keep_alive_worker(stop_event):
    """
    Sendet periodisch Anfragen an die ÖFFENTLICHE URL der App.
    """
    app_name = os.environ.get("FLY_APP_NAME")

    if app_name:
        target_url = f"https://{app_name}.fly.dev/"
    else:
        return

    log_info(f"[Keep-Alive] Gestartet. Pinge {target_url} alle 20s.")

    while not stop_event.is_set():
        try:
            requests.get(target_url, timeout=10)
        except Exception:  # pylint: disable=broad-exception-caught
            pass

        if stop_event.wait(timeout=20):
            break

    log_info("[Keep-Alive] Beendet.")


def _cleanup_old_reports(output_dir, days=14):
    """Löscht alle Dateien im Output-Ordner, die älter als 'days' sind."""
    now = time.time()
    cutoff = now - (days * 86400)  # 86400 Sekunden = 1 Tag
    count = 0

    if not os.path.exists(output_dir):
        return

    for root, _, files in os.walk(output_dir):
        for file in files:
            # Das Haupt-Log behalten wir sicherheitshalber
            if file == "audit.log":
                continue
            fpath = os.path.join(root, file)
            try:
                if os.path.isfile(fpath) and os.stat(fpath).st_mtime < cutoff:
                    os.remove(fpath)
                    count += 1
            except OSError as err:
                log_error(f"Fehler beim Löschen alter Datei {fpath}: {err}")

    if count > 0:
        log_info(f"🧹 Auto-Cleanup: {count} alte Datei(en) (> {days} Tage) gelöscht.")


def _run_job(url, max_pages, depth):
    """Worker Funktion, die den Audit durchführt."""

    stop_event = threading.Event()
    keep_alive_thread = threading.Thread(target=_keep_alive_worker, args=(stop_event,))
    keep_alive_thread.daemon = True
    keep_alive_thread.start()

    try:
        cfg = load_config()
        output_root = cfg["active_paths"]["output"]
        os.makedirs(output_root, exist_ok=True)

        # 🚀 NEU: Automatische Bereinigung vor Start!
        _cleanup_old_reports(output_root, days=14)

        log_info(f"Job gestartet: {url}")

        facade = AuditFacade()
        result_path = facade.run_full_audit(url, max_pages, depth)

        if result_path and os.path.exists(result_path):
            filename = os.path.basename(result_path)
            dest_path = os.path.join(output_root, filename)
            shutil.copy2(result_path, dest_path)
            log_info(f"✅ Report gesichert auf Volume: {dest_path}")

        log_info(f"Job beendet. Datei: {result_path}")

    except Exception as err:  # pylint: disable=broad-exception-caught
        log_error(f"Job Fehler: {err}")

    finally:
        stop_event.set()
        keep_alive_thread.join(timeout=2)
        log_info("Prozess fertig. Auto-Stop darf jetzt greifen.")
