"""Service zur sequenziellen Verarbeitung und Prüfung von PDFs."""

import json
import os
import subprocess
from datetime import datetime
from urllib.parse import urlparse

import PyPDF2
import requests

from core.utils.error_utils import log_error, log_info


def get_verapdf_version(verapdf_path):
    """Ermittelt die Version von VeraPDF."""
    cmd = [
        "java",
        "-cp",
        verapdf_path,
        "org.verapdf.apps.GreenfieldCliWrapper",
        "--version",
    ]
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10, check=False
        )
        out = res.stdout.strip()
        if out:
            return out.splitlines()[0]
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    return "1.28.2"


def _run_verapdf(verapdf_path, lpath, profile=None, timeout=120):
    """Führt den VeraPDF-Check für ein PDF aus."""
    cmd = [
        "java",
        "-cp",
        verapdf_path,
        "org.verapdf.apps.GreenfieldCliWrapper",
        "--format",
        "text",
    ]
    if profile:
        cmd.extend(["--profile", profile])
    else:
        cmd.extend(["--flavour", "ua1"])
    cmd.append(lpath)
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        out = res.stdout.strip().replace(lpath, "").replace("  ", " ").strip()
        return ("PASS" if "PASS" in out else "FAIL"), out[:200]
    except subprocess.TimeoutExpired:
        return "ERROR", "Timeout"


def _extract_pdf_info(filepath):
    """Extrahiert Autor und Erstelldatum aus dem PDF."""
    author, creation_date = "Unknown", "Unknown"
    try:
        with open(filepath, "rb") as f:
            meta = PyPDF2.PdfReader(f).metadata
            if meta:
                if meta.get("/Author"):
                    author = str(meta.get("/Author")).strip()
                d = meta.get("/CreationDate")
                if d and isinstance(d, str) and d.startswith("D:"):
                    try:
                        creation_date = datetime.strptime(d[2:10], "%Y%m%d").strftime(
                            "%b. %d, %Y"
                        )
                    except ValueError:
                        creation_date = d[2:10]
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    return author, creation_date


def process_pdf_links(link_file, output_json, temp_dir, verapdf_path):
    """Liest URLs ein, lädt PDFs herunter und prüft sie auf Barrierefreiheit."""
    os.makedirs(temp_dir, exist_ok=True)
    with open(link_file, "r", encoding="utf-8") as f:
        urls = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    results = []
    for i, url in enumerate(urls, 1):
        fname = os.path.basename(urlparse(url).path) or f"file_{i}.pdf"
        lpath = os.path.join(temp_dir, fname)
        log_info(f"⏳ Verarbeite PDF[{i}/{len(urls)}]: {fname}")

        entry = {
            "url": url,
            "filename": fname,
            "status_strict": "UNKNOWN",
            "status": "UNKNOWN",
            "details": "",
            "author": "Unknown",
            "date": "Unknown",
        }

        try:
            resp = requests.get(url, stream=True, timeout=60)
            with open(lpath, "wb") as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)

            entry["author"], entry["date"] = _extract_pdf_info(lpath)
            entry["status_strict"], entry["details"] = _run_verapdf(verapdf_path, lpath)
            entry["status"] = entry["status_strict"]

        except Exception as err:  # pylint: disable=broad-exception-caught
            log_error(f"Fehler bei {fname}: {err}")
            entry["details"] = str(err)
        finally:
            if os.path.exists(lpath):
                os.remove(lpath)

        results.append(entry)

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    return results
