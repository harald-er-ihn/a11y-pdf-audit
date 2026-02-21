"""
Controller zur Steuerung von Hintergrundprozessen.
Enthält Keep-Alive Logik (Public Ping) und Dateiverwaltung.
"""

import logging
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
    # daemon=False ist wichtig, damit der Thread nicht sofort stirbt
    thread = threading.Thread(target=_run_job, args=(url, max_pages, depth))
    thread.daemon = True
    thread.start()


def _keep_alive_worker(stop_event):
    """
    Sendet periodisch Anfragen an die ÖFFENTLICHE URL der App.
    Nur Traffic, der über den Fly-Proxy kommt, verhindert den Auto-Stop.
    Lokale Requests (localhost) werden vom Proxy ignoriert!
    """
    app_name = os.environ.get("FLY_APP_NAME")

    # WICHTIG: Wir müssen die öffentliche URL nutzen!
    if app_name:
        target_url = f"https://{app_name}.fly.dev/"
    else:
        # Lokal macht Keep-Alive keinen Sinn/ist nicht nötig
        return

    log_info(f"[Keep-Alive] Gestartet. Pinge {target_url} alle 20s.")

    while not stop_event.is_set():
        try:
            # Kurzer Timeout, wir wollen nur den Proxy "wecken"
            requests.get(target_url, timeout=10)
        except Exception as e:
            # Fehler ignorieren, Hauptsache versucht
            # log_info(f"[Keep-Alive] Ping Fehler: {e}") # Optional debug
            pass

        # 20 Sekunden warten (Fly Timeout ist oft ca 5 Min, 20s ist sicher)
        if stop_event.wait(timeout=20):
            break

    log_info("[Keep-Alive] Beendet.")


def _run_job(url, max_pages, depth):
    """Worker Funktion, die den Audit durchführt."""

    # 1. Keep-Alive starten
    stop_event = threading.Event()
    keep_alive_thread = threading.Thread(target=_keep_alive_worker, args=(stop_event,))
    keep_alive_thread.daemon = True
    keep_alive_thread.start()

    facade = AuditFacade()

    try:
        log_info(f"Job gestartet: {url}")

        # Audit durchführen (kann Stunden dauern)
        result_path = facade.run_full_audit(url, max_pages, depth)

        # 2. Report ins persistente Output-Verzeichnis kopieren
        if result_path and os.path.exists(result_path):
            cfg = load_config()
            # Der "output" Pfad aus der Config ist /app/output (das Volume)
            output_root = cfg["active_paths"]["output"]

            # Sicherstellen, dass das Zielverzeichnis existiert
            os.makedirs(output_root, exist_ok=True)

            # Zieldateiname
            filename = os.path.basename(result_path)
            dest_path = os.path.join(output_root, filename)

            shutil.copy2(result_path, dest_path)
            log_info(f"✅ Report gesichert auf Volume: {dest_path}")

        log_info(f"Job beendet. Datei: {result_path}")

    except Exception as e:  # pylint: disable=broad-exception-caught
        log_error(f"Job Fehler: {e}")

    finally:
        # 3. Keep-Alive beenden -> Maschine darf jetzt schlafen
        stop_event.set()
        keep_alive_thread.join(timeout=2)
        log_info("Prozess fertig. Auto-Stop darf jetzt greifen.")
