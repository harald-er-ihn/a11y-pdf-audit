"""
Definiert die Routen für die Webanwendung.
"""

import logging
import os
import shutil

from flask import (Blueprint, abort, jsonify, render_template, request,
                   send_from_directory)

from core.controller import start_audit_background
from core.utils.config_loader import load_config
from core.utils.error_utils import (log_error, log_info, log_warning,
                                    setup_logging)

# Initiale Config laden um Pfade zu kennen
try:
    _CONFIG = load_config()
    _OUTPUT_DIR = _CONFIG["active_paths"]["output"]
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    setup_logging(log_dir=_OUTPUT_DIR)
except Exception:
    setup_logging()

main_bp = Blueprint("main", __name__)


@main_bp.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@main_bp.route("/ueber", methods=["GET"])
def about():
    return render_template("ueber.html")


@main_bp.route("/sprachen-languages", methods=["GET"])
def languages():
    return render_template("sprachen_languages.html")


@main_bp.route("/start-audit", methods=["POST"])
def start_audit():
    url = request.form.get("url")
    try:
        max_p = int(request.form.get("max_pages", 10))
        depth = int(request.form.get("depth", 1))
    except ValueError:
        return "Ungültige Eingabe", 400

    if url:
        start_audit_background(url, max_p, depth)
        return render_template("success.html", url=url)
    return "URL fehlt", 400


@main_bp.route("/reports")
def list_reports():
    """Listet verfügbare PDF-Berichte."""
    cfg = load_config()
    vol_root = cfg["active_paths"]["output"]
    rep_dir = os.path.join(vol_root, "reports")

    # Sicherstellen, dass Verzeichnisse existieren
    os.makedirs(rep_dir, exist_ok=True)

    files = []
    try:
        # Wir sammeln PDFs nur aus dem Root und dem Reports Ordner
        candidates = set()

        # 1. Aus dem Reports-Unterordner
        if os.path.exists(rep_dir):
            for f in os.listdir(rep_dir):
                if f.lower().endswith(".pdf"):
                    candidates.add(f)

        # 2. Aus dem Hauptverzeichnis (Volume Root)
        # Hier landet die finale Kopie
        if os.path.exists(vol_root):
            for f in os.listdir(vol_root):
                if f.lower().endswith(".pdf"):
                    candidates.add(f)

        files = sorted(list(candidates), reverse=True)
        # Debug Log, damit wir sehen was passiert
        # log_info(f"UI Listing: {len(files)} PDFs gefunden in {vol_root}")

    except OSError as e:
        log_error(f"Fehler beim Listen: {e}")

    return render_template("reports.html", files=files)


@main_bp.route("/download/<path:filename>")
def download_file(filename):
    if not filename.lower().endswith(".pdf"):
        abort(403)

    cfg = load_config()
    output_root = cfg["active_paths"]["output"]
    report_dir = os.path.join(output_root, "reports")

    # Versuch 1: Root (Volume)
    if os.path.exists(os.path.join(output_root, filename)):
        return send_from_directory(output_root, filename, as_attachment=True)

    # Versuch 2: Reports Ordner
    return send_from_directory(report_dir, filename, as_attachment=True)


@main_bp.route("/api/logs")
def get_logs():
    cfg = load_config()
    # Wichtig: Dateiname muss mit setup_logging übereinstimmen
    log_file = os.path.join(cfg["active_paths"]["output"], "audit.log")

    if not os.path.exists(log_file):
        return jsonify(
            {"logs": f"Logdatei nicht gefunden: {log_file} (Warte auf Start...)"}
        )

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            # Lese die letzten 4KB (reicht für ca. 40-50 Zeilen) effizient
            # statt alles in den Speicher zu laden
            f.seek(0, 2)  # Gehe ans Ende
            size = f.tell()
            f.seek(max(size - 4096, 0), 0)  # Gehe 4KB zurück
            lines = f.readlines()
            # Falls wir mitten in einer Zeile gestartet sind, erste Zeile verwerfen
            if len(lines) > 1 and size > 4096:
                lines = lines[1:]

            return jsonify({"logs": "".join(lines)})
    except Exception as e:
        return jsonify({"logs": f"Fehler beim Lesen: {e}"})


@main_bp.route("/cleanup", methods=["POST"])
def cleanup_files():
    """Löscht Berichte, BEHÄLT aber das Log-File."""
    cfg = load_config()
    output_root = cfg["active_paths"]["output"]
    log_file_name = "audit.log"

    count = 0
    try:
        if os.path.exists(output_root):
            for item in os.listdir(output_root):
                path = os.path.join(output_root, item)

                # WICHTIG: Log-Datei nicht löschen!
                if item == log_file_name:
                    continue

                try:
                    if os.path.isfile(path) or os.path.islink(path):
                        os.unlink(path)
                        count += 1
                    elif os.path.isdir(path):
                        shutil.rmtree(path)
                        count += 1
                except Exception as e:
                    log_error(f"Konnte {item} nicht löschen: {e}")

        log_info(f"🧹 Cleanup: {count} Objekte gelöscht (Logs behalten).")

        # Leeren Ordnerstruktur wiederherstellen
        os.makedirs(os.path.join(output_root, "reports"), exist_ok=True)

        return render_template("success.html", url="System Cleaned")
    except Exception as e:
        log_error(f"Cleanup Fatal: {e}")
        return f"Error: {e}", 500
