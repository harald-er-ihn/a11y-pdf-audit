"""
Service zur Verarbeitung (Download, Prüfung) von PDF-Dateien.
"""

import json
import os
import shutil
import subprocess
from datetime import datetime
from urllib.parse import urlparse

import requests
from PyPDF2 import PdfReader

# Wir nutzen jetzt das zentrale Logging, damit es im Web-Fenster erscheint
from core.utils.error_utils import log_error, log_info


def get_verapdf_version(verapdf_cli_path):
    """Holt die Version von VeraPDF."""
    try:
        cmd = [
            "java",
            "-cp",
            verapdf_cli_path,
            "org.verapdf.apps.GreenfieldCliWrapper",
            "--version",
        ]
        # Timeout auf 30 Sekunden für Version Check
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, check=False
        )
        return result.stdout.strip()
    except (subprocess.SubprocessError, OSError) as e:
        return f"Version error: {e}"


def _get_pdf_metadata(local_path):
    """Liest Autor und Erstellungsdatum via PyPDF2 aus."""
    meta_info = {"author": "Unknown", "date": "Unknown"}
    try:
        reader = PdfReader(local_path)
        if reader.metadata:
            # Autor holen
            if "/Author" in reader.metadata:
                meta_info["author"] = (
                    str(reader.metadata["/Author"]).strip() or "Unknown"
                )

            # Datum holen
            if "/CreationDate" in reader.metadata:
                d_raw = (
                    str(reader.metadata["/CreationDate"])
                    .replace("D:", "")
                    .split("+")[0]
                    .split("Z")[0]
                )
                try:
                    # Meistens YYYYMMDDHHMMSS
                    dt = datetime.strptime(d_raw[:14], "%Y%m%d%H%M%S")
                    meta_info["date"] = dt.strftime("%b. %d, %Y")
                except ValueError:
                    meta_info["date"] = d_raw  # Fallback
    except Exception:
        pass

    return meta_info


def _run_verapdf(verapdf_cli_path, local_path):
    """Führt den VeraPDF Check für eine Datei aus."""
    cmd = [
        "java",
        "-cp",
        verapdf_cli_path,
        "org.verapdf.apps.GreenfieldCliWrapper",
        "--format",
        "text",
        local_path,
    ]
    try:
        # Timeout auf 120 Sekunden erhöht
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, check=False
        )
        output = proc.stdout.strip() or proc.stderr.strip()

        first_line = output.split("\n")[0] if output else "ERROR: No output"

        # Pfad aus Output entfernen für sauberen Report
        clean_msg = first_line.replace(local_path, "").strip()
        clean_msg = " ".join(clean_msg.split())

        profile = clean_msg.split()[-1] if len(clean_msg.split()) > 1 else "?"

        if "PASS" in first_line:
            return "PASS", clean_msg, profile
        if "FAIL" in first_line:
            return "FAIL", clean_msg, profile

        return "ERROR", f"VeraPDF Error: {clean_msg}", "?"

    except subprocess.TimeoutExpired:
        return "ERROR", "VeraPDF Timeout (120s exceeded)", "?"
    except (subprocess.SubprocessError, OSError) as e:
        return "ERROR", str(e), "?"


def _process_single_pdf(url, index, total, temp_dir, verapdf_cli_path):
    """Lädt ein einzelnes PDF und prüft es."""
    filename = os.path.basename(urlparse(url).path) or f"doc_{index}.pdf"
    local_path = os.path.join(temp_dir, filename)

    # WICHTIG: log_info statt print, damit es im Web-Terminal erscheint!
    log_info(f"[{index}/{total}] ⏳ Prüfe: {filename}")

    entry = {
        "url": url,
        "filename": filename,
        "status": "UNKNOWN",
        "details": "",
        "profile": "",
        "author": "Unknown",
        "date": "Unknown",
    }

    try:
        # Download
        headers = {"User-Agent": "a11y-pdf-audit-bot"}
        with requests.get(url, headers=headers, stream=True, timeout=15) as r:
            r.raise_for_status()
            with open(local_path, "wb") as f:
                shutil.copyfileobj(r.raw, f)

        # 1. Metadaten extrahieren
        meta = _get_pdf_metadata(local_path)
        entry["author"] = meta["author"]
        entry["date"] = meta["date"]

        # 2. VeraPDF Check
        status, details, profile = _run_verapdf(verapdf_cli_path, local_path)
        entry.update({"status": status, "details": details, "profile": profile})

        # Kurzes Ergebnis-Log
        if status == "PASS":
            log_info(f"   ✅ PASS: {filename}")
        elif status == "FAIL":
            # Details kürzen für Log
            short_details = (details[:50] + "..") if len(details) > 50 else details
            log_info(f"   ❌ FAIL: {short_details}")
        else:
            log_info(f"   ⚠️ ERROR: {details}")

    except requests.RequestException as e:
        err_msg = str(e)
        entry.update({"status": "ERROR", "details": err_msg})
        log_error(f"   Download Fehler: {err_msg}")

    finally:
        if os.path.exists(local_path):
            os.remove(local_path)

    return entry


def process_pdf_links(link_list_file, output_json, temp_dir, verapdf_path):
    """Hauptfunktion zur Verarbeitung der Linkliste."""
    os.makedirs(temp_dir, exist_ok=True)

    if not os.path.exists(link_list_file):
        log_error(f"Link-Datei fehlt: {link_list_file}")
        return []

    with open(link_list_file, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    results = []
    total = len(urls)

    log_info(f"Starte VeraPDF Prüfung für {total} Dateien...")

    for i, url in enumerate(urls, 1):
        res = _process_single_pdf(url, i, total, temp_dir, verapdf_path)
        results.append(res)

    # Sortierung: PASS(0) -> FAIL(1) -> Rest(2)
    def sort_key(item):
        return {"PASS": 0, "FAIL": 1}.get(item["status"], 2)

    results.sort(key=sort_key)

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    return results
