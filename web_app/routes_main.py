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

try:
    _CONFIG = load_config()
    _OUTPUT_DIR = _CONFIG["active_paths"]["output"]
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    setup_logging(log_dir=_OUTPUT_DIR)
except Exception:  # pylint: disable=broad-exception-caught
    _CONFIG = {}
    setup_logging()

main_bp = Blueprint("main", __name__)


@main_bp.route("/", methods=["GET"])
def index():
    """Zeigt die Startseite."""
    crawler_cfg = _CONFIG.get("crawler", {})
    return render_template(
        "index.html",
        default_max_pages=crawler_cfg.get("default_max_pages", 3),
        default_depth=crawler_cfg.get("default_depth", 1),
        max_pages_limit=crawler_cfg.get("default_max_pages", 3),
        max_depth_limit=crawler_cfg.get("default_depth", 3),
    )


@main_bp.route("/licenses", methods=["GET"])
def licenses():
    """Zeigt die Lizenzen-Seite."""
    return render_template("licenses.html")


@main_bp.route("/german-law")
def german_law():
    """Zeigt die Seite mit den rechtlichen Hinweisen an."""
    return render_template("german_law.html")


@main_bp.route("/start-audit", methods=["POST"])
def start_audit():
    """Startet den Audit-Prozess."""
    url = request.form.get("url")
    crawler_cfg = _CONFIG.get("crawler", {})
    default_max_pages = crawler_cfg.get("default_max_pages", 3)
    default_depth = crawler_cfg.get("default_depth", 1)

    try:
        max_p = int(request.form.get("max_pages", default_max_pages))
        depth = int(request.form.get("depth", default_depth))
    except ValueError:
        return "Ungültige Eingabe", 400

    max_p = min(max_p, default_max_pages)
    depth = min(depth, 3)

    if url:
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            requests.get(
                url, headers=headers, timeout=3, allow_redirects=True, stream=True
            )
        except requests.exceptions.ConnectionError:
            log_error(f"URL-Validierung: Server {url} nicht gefunden.")
            return (
                render_template(
                    "error.html", error=f"Die URL '{url}' konnte nicht gefunden werden."
                ),
                400,
            )
        except requests.RequestException as err:
            log_warning(
                f"URL-Validierung Timeout für {url}: {err} -> Starte Job trotzdem."
            )

        start_audit_background(url, max_p, depth)
        return render_template("success.html", url=url)

    return "URL fehlt", 400


@main_bp.route("/about", methods=["GET"])
def about():
    """Zeigt die Über-Seite."""
    return render_template("about.html")


@main_bp.route("/screenreadable", methods=["GET"])
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
    """Listet verfügbare PDF-Berichte auf."""
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
        files = [f for f in candidates if f.lower().endswith(".pdf")]

        def sort_key(filename):
            parts = filename.split("_")
            if len(parts) > 1:
                return parts[1]
            return filename

        files.sort(key=sort_key, reverse=True)
    except OSError as err:
        log_error(f"Fehler beim Listen der Dateien: {err}")

    return render_template("reports.html", files=files)


@main_bp.route("/download/<path:filename>")
def download_file(filename):
    """Download Route."""
    if not filename.lower().endswith(".pdf"):
        abort(403)

    cfg = load_config()
    out_root = cfg["active_paths"]["output"]
    rep_dir = os.path.join(out_root, "reports")

    if os.path.exists(os.path.join(out_root, filename)):
        response = send_from_directory(out_root, filename, as_attachment=True)
    else:
        response = send_from_directory(rep_dir, filename, as_attachment=True)

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
    try:
        count = 0
        if os.path.exists(output_root):
            for item in os.listdir(output_root):
                if item == "audit.log":
                    continue
                path = os.path.join(output_root, item)
                if os.path.isfile(path):
                    os.unlink(path)
                    count += 1
                elif os.path.isdir(path):
                    shutil.rmtree(path)
                    count += 1
        log_info(f"🧹 Cleanup: {count} Objekte gelöscht.")
        os.makedirs(os.path.join(output_root, "reports"), exist_ok=True)
        return render_template("success.html", url="System Cleaned")
    except Exception as err:  # pylint: disable=broad-exception-caught
        return f"Error: {err}", 500
