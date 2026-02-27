"""
Service zur sequenziellen Verarbeitung und Prüfung von PDFs.
"""
import json
import os
from urllib.parse import urlparse

import requests

from core.services.pdf_converter import run_improvement


def _run_verapdf(verapdf_path, lpath, profile=None, timeout=120):
    """Führt VeraPDF-Check aus."""
    import subprocess

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
    except:
        return "ERROR", "Timeout/Crash"


def _process_single_pdf(url, idx, ctx):
    """Verarbeitet ein einzelnes PDF."""
    fname = os.path.basename(urlparse(url).path) or f"file_{idx}.pdf"
    lpath = os.path.join(ctx["temp_dir"], fname)
    entry = {"url": url, "filename": fname, "status": "UNKNOWN", "repaired": False}

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
    with open(link_file, "r") as f:
        urls = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    ctx = {"temp_dir": temp_dir, "v_path": verapdf_path, "force_ai": force_ai}
    results = [_process_single_pdf(u, i, ctx) for i, u in enumerate(urls, 1)]

    with open(output_json, "w") as f:
        json.dump(results, f, indent=2)
    return results
