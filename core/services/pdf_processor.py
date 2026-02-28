"""
Service zur sequenziellen Verarbeitung und Prüfung von PDFs.
"""

import json
import os
import subprocess
from urllib.parse import urlparse

import requests

from core.services.pdf_converter import run_improvement
from core.utils.config_loader import load_config
from core.utils.error_utils import log_error


def get_verapdf_version(verapdf_cli_path):
    """Holt die Version von VeraPDF (Fixes Facade Import)."""
    cfg = load_config()
    cmd = [
        cfg["audit"].get("java_cmd", "java"),
        "-cp",
        verapdf_cli_path,
        "org.verapdf.apps.GreenfieldCliWrapper",
        "--version",
    ]
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, check=False
        )
        return res.stdout.strip() if res.stdout else "VeraPDF 1.2x"
    except (subprocess.SubprocessError, FileNotFoundError):
        return "VeraPDF (CLI nicht gefunden)"


def _run_verapdf(verapdf_path, lpath, profile=None, timeout=120):
    """Führt VeraPDF-Check aus."""

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
        out = res.stdout.strip()
        return ("PASS" if "PASS" in out else "FAIL"), out[:200]
    except subprocess.TimeoutExpired:
        return "ERROR", "Timeout"


def _process_single_pdf(url, idx, ctx):
    """Verarbeitet ein einzelnes PDF."""
    fname = os.path.basename(urlparse(url).path) or f"file_{idx}.pdf"
    lpath = os.path.join(ctx["temp_dir"], fname)
    entry = {
        "url": url,
        "filename": fname,
        "status": "UNKNOWN",
        "status_strict": "UNKNOWN",
        "details": "",
        "repaired": False,
        "author": "Unknown",
        "date": "Unknown",
    }

    try:
        # Download
        with requests.get(url, stream=True, timeout=20) as r:
            with open(lpath, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)

        # 1. Audit Original
        entry["status"], entry["details"] = _run_verapdf(ctx["v_path"], lpath)

        # 2. Verbesserung bei Bedarf
        if entry["status"] == "FAIL":
            improved_path = os.path.join(ctx["temp_dir"], f"IMPROVED_{fname}")
            if run_improvement(lpath, improved_path, force_ai=ctx["force_ai"]):
                entry["repaired"] = True
                entry["repaired_path"] = improved_path
                # Erfolgskontrolle
                entry["status_after"], _ = _run_verapdf(ctx["v_path"], improved_path)
    except Exception as e:
        entry["status"] = "ERROR"
        entry["details"] = str(e)
    finally:
        if os.path.exists(lpath):
            os.remove(lpath)
    return entry


def process_pdf_links(link_file, output_json, temp_dir, verapdf_path, force_ai=False):
    """Steuert die Verarbeitung aller Links."""
    os.makedirs(temp_dir, exist_ok=True)
    with open(link_file, "r", encoding="utf-8") as f:
        urls = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    ctx = {"temp_dir": temp_dir, "v_path": verapdf_path, "force_ai": force_ai}
    results = [_process_single_pdf(u, i, ctx) for i, u in enumerate(urls, 1)]

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    return results
