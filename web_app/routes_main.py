"""
Definiert die Routen für die Webanwendung.
"""

import os
import shutil

import requests
from flask import (Blueprint, abort, jsonify, redirect, render_template,
                   request, send_from_directory, url_for)

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
except Exception:  # pylint: disable=broad-exception-caught
    setup_logging()

main_bp = Blueprint("main", __name__)


@main_bp.route("/", methods=["GET"])
def index():
    """Zeigt die Startseite."""
    return render_template("index.html")


@main_bp.route("/start-audit", methods=["POST"])
def start_audit():
    """Startet den Audit-Prozess inkl. intelligenter URL-Validierung."""
    url = request.form.get("url")
    try:
        max_p = int(request.form.get("max_pages", 10))
        depth = int(request.form.get("depth", 1))
    except ValueError:
        return "Ungültige Eingabe", 400

    if url:
        url = url.strip()

        # 1. URL bereinigen und https:// ergänzen, falls nötig
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        # 2. URL auf Erreichbarkeit prüfen (Ping)
        try:
            # Wir tarnen uns beim Ping als normaler Browser, um Cloudflare etc. nicht sofort zu triggern
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            }
            # stream=True sorgt dafür, dass wir nur den Header laden und nicht die ganze Seite
            requests.get(
                url, headers=headers, timeout=5, allow_redirects=True, stream=True
            )
            # WICHTIG: Wir rufen absichtlich KEIN raise_for_status() auf!
            # Wenn ein Server mit 403 (Forbidden) oder 500 antwortet, bedeutet das:
            # Die URL existiert! Der Job darf also starten.

        except requests.exceptions.ConnectionError:
            # Das passiert nur, wenn es die Domain wirklich nicht gibt (DNS Fehler)
            log_error(f"URL-Validierung: Server {url} nicht gefunden.")
            return (
                render_template(
                    "error.html",
                    error=f"Die URL '{url}' konnte nicht gefunden werden. Bitte prüfe auf Tippfehler.",
                ),
                400,
            )
        except requests.RequestException as err:
            # Bei Timeouts lassen wir den Job trotzdem starten. Der Crawler hat ein eigenes Fehler-Handling.
            log_warning(
                f"URL-Validierung Timeout für {url}: {err} -> Starte Job trotzdem."
            )

        # 3. Audit starten, da URL valide ist
        start_audit_background(url, max_p, depth)
        return render_template("success.html", url=url)

    return "URL fehlt", 400


@main_bp.route("/about", methods=["GET"])
def about():
    """Zeigt die Über-Seite."""
    return render_template("about.html")


@main_bp.route("/screenreadable", methods=["GET"])
@main_bp.route("/screenreadable.html", methods=["GET"])
def screenreadable():
    """Zeigt die Details zum ScreenReadable-Profil."""
    return render_template("screenreadable.html")


@main_bp.route("/ueber", methods=["GET"])
@main_bp.route("/ueber.html", methods=["GET"])
def redirect_ueber():
    """Leitet alte URL /ueber.html auf /about um."""
    return redirect(url_for("main.about"), code=301)


@main_bp.route("/sprachen-languages", methods=["GET"])
def languages():
    """Zeigt die Sprachen-Seite."""
    return render_template("sprachen_languages.html")


@main_bp.route("/reports")
def list_reports():
    """Listet verfügbare PDF-Berichte."""
    cfg = load_config()
    vol_root = cfg["active_paths"]["output"]
    rep_dir = os.path.join(vol_root, "reports")
    os.makedirs(rep_dir, exist_ok=True)

    files = []
    try:
        candidates = set()
        if os.path.exists(rep_dir):
            candidates.update(os.listdir(rep_dir))
        if os.path.exists(vol_root):
            candidates.update(os.listdir(vol_root))

        files = sorted(
            [f for f in candidates if f.lower().endswith((".pdf", ".zip"))],
            reverse=True,
        )
    except OSError as err:
        log_error(f"Fehler beim Listen: {err}")

    return render_template("reports.html", files=files)


@main_bp.route("/download/<path:filename>")
def download_file(filename):
    """Download Route."""
    if not (filename.lower().endswith(".pdf") or filename.lower().endswith(".zip")):
        log_warning(f"Illegaler Download: {filename}")
        abort(403)

    cfg = load_config()
    out_root = cfg["active_paths"]["output"]
    rep_dir = os.path.join(out_root, "reports")

    # Datei-Pfad ermitteln und Response-Objekt erstellen
    if os.path.exists(os.path.join(out_root, filename)):
        response = send_from_directory(out_root, filename, as_attachment=True)
    else:
        response = send_from_directory(rep_dir, filename, as_attachment=True)

    # SECURITY & SEO FIX: Verhindert, dass Spider und Suchmaschinen
    # die dynamischen PDF-Reports indexieren und Bandbreite fressen.
    response.headers["X-Robots-Tag"] = "noindex, nofollow"

    return response


@main_bp.route("/api/logs")
def get_logs():
    """API für Logs."""
    cfg = load_config()
    log_file = os.path.join(cfg["active_paths"]["output"], "audit.log")

    if not os.path.exists(log_file):
        return jsonify({"logs": "Warte auf Start..."})

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(size - 4096, 0), 0)
            lines = f.readlines()
            if len(lines) > 1 and size > 4096:
                lines = lines[1:]
            return jsonify({"logs": "".join(lines)})
    except Exception as err:  # pylint: disable=broad-exception-caught
        return jsonify({"logs": f"Fehler: {err}"})


@main_bp.route("/cleanup", methods=["POST"])
def cleanup_files():
    """Bereinigt den Output-Ordner."""
    cfg = load_config()
    output_root = cfg["active_paths"]["output"]
    log_file_name = "audit.log"
    count = 0
    try:
        if os.path.exists(output_root):
            for item in os.listdir(output_root):
                path = os.path.join(output_root, item)
                if item == log_file_name:
                    continue
                try:
                    if os.path.isfile(path) or os.path.islink(path):
                        os.unlink(path)
                        count += 1
                    elif os.path.isdir(path):
                        shutil.rmtree(path)
                        count += 1
                except OSError as err:
                    log_error(f"Konnte {item} nicht löschen: {err}")
        log_info(f"🧹 Cleanup: {count} Objekte gelöscht.")
        os.makedirs(os.path.join(output_root, "reports"), exist_ok=True)
        return render_template("success.html", url="System Cleaned")
    except Exception as err:  # pylint: disable=broad-exception-caught
        return f"Error: {err}", 500
