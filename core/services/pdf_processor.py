"""
Service zur Verarbeitung (Download, Prüfung) von PDF-Dateien.
"""

import json
import os
import shutil
import subprocess
import time
from datetime import datetime
from urllib.parse import urlparse

import requests
from PyPDF2 import PdfReader

from core.utils.config_loader import load_config
from core.utils.error_utils import log_error, log_info, log_warning


def get_verapdf_version(verapdf_cli_path):
    """Holt die Version von VeraPDF mit Retry und dynamischem Timeout."""
    cfg = load_config()
    timeout_version = cfg["audit"].get("timeout_version_sec", 30)
    retries = cfg["audit"].get("verapdf_retries", 1)
    t_factor = cfg["audit"].get("timeout_factor", 4)

    # 🚀 Config-Driven CLI Command
    cmd = [cfg["audit"].get("java_cmd", "java")]
    for p in cfg["audit"].get("verapdf_params", []):
        cmd.append(p.replace("{jar_path}", verapdf_cli_path))
    cmd.append("--version")

    current_timeout = timeout_version

    for attempt in range(retries + 1):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=current_timeout,
                check=False,
            )  # nosec
            if result.stdout:
                return result.stdout.strip()
            return "VeraPDF (Version unbekannt)"
        except subprocess.TimeoutExpired:
            if attempt < retries:
                log_warning(
                    f"⏱️ Version-Timeout. Versuch {attempt+2} mit {current_timeout * t_factor}s!"
                )
                current_timeout *= t_factor
                time.sleep(2)
                continue
            return f"VeraPDF (Timeout nach {current_timeout}s)"
        except (subprocess.SubprocessError, OSError) as err:
            return f"VeraPDF Error: {err}"


def _parse_creation_date(metadata):
    """Hilfsfunktion zum Parsen des Datums."""
    if "/CreationDate" not in metadata:
        return "Unknown"

    # C0207 Optimized string manipulation
    raw = str(metadata["/CreationDate"]).replace("D:", "")
    raw = raw.split("+", maxsplit=1)[0].split("Z", maxsplit=1)[0]

    try:
        dt_obj = datetime.strptime(raw[:14], "%Y%m%d%H%M%S")
        return dt_obj.strftime("%b. %d, %Y")
    except ValueError:
        return raw


def _get_pdf_metadata(local_path):
    """Liest Autor und Erstellungsdatum via PyPDF2 aus."""
    meta = {"author": "Unknown", "date": "Unknown"}
    try:
        reader = PdfReader(local_path)
        if reader.metadata:
            if "/Author" in reader.metadata:
                author = str(reader.metadata["/Author"]).strip()
                meta["author"] = author or "Unknown"

            meta["date"] = _parse_creation_date(reader.metadata)
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    return meta


def _parse_verapdf_output(output, local_path):
    """Hilfsfunktion zum Auswerten des Konsolen-Outputs von veraPDF."""
    first_line = output.split("\n")[0] if output else "ERROR: No output"
    clean_msg = first_line.replace(local_path, "").strip()
    clean_msg = " ".join(clean_msg.split())
    profile = clean_msg.split()[-1] if len(clean_msg.split()) > 1 else "?"

    status = "ERROR"
    if "PASS" in first_line:
        status = "PASS"
    elif "FAIL" in first_line:
        status = "FAIL"
    else:
        clean_msg = f"VeraPDF Error: {clean_msg}"

    return status, clean_msg, profile


def _run_verapdf(verapdf_cli_path, local_path, profile_path=None, forced_timeout=None):
    """Führt den VeraPDF Check für eine Datei aus."""
    cfg = load_config()
    timeout_check = forced_timeout or cfg["audit"].get("timeout_check_sec", 120)
    retries = cfg["audit"].get("verapdf_retries", 1)

    # 🚀 FIX: t_factor aus der Config laden!
    t_factor = cfg["audit"].get("timeout_factor", 4)

    cmd = [
        "java",
        "-cp",
        verapdf_cli_path,
        "org.verapdf.apps.GreenfieldCliWrapper",
        "--format",
        "text",
    ]

    if profile_path and os.path.exists(profile_path):
        cmd.extend(["--profile", profile_path])
    else:
        cmd.extend(["--flavour", "ua1"])

    cmd.append(local_path)
    current_timeout = timeout_check

    for attempt in range(retries + 1):
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=current_timeout,
                check=False,
            )  # nosec
            output = proc.stdout.strip() or proc.stderr.strip()
            status, clean_msg, profile = _parse_verapdf_output(output, local_path)
            return status, clean_msg, profile, current_timeout

        except subprocess.TimeoutExpired:
            if attempt < retries:
                run_name = "SR" if profile_path else "Strict"
                fname = os.path.basename(local_path)
                log_warning(
                    f"⏱️ {run_name}-Timeout bei {fname}. Versuch {attempt+2} mit {current_timeout * t_factor}s!"
                )
                current_timeout *= t_factor
                time.sleep(5)
                continue

            return (
                "ERROR",
                f"VeraPDF Timeout exceeded ({current_timeout}s)",
                "?",
                current_timeout,
            )
        except (subprocess.SubprocessError, OSError) as err:
            return "ERROR", str(err), "?", current_timeout


def _download_file(url, local_path):
    """Hilfsfunktion zum Herunterladen der PDF (mit Retry bei Abbrüchen)."""
    headers = {"User-Agent": "a11y-pdf-audit-bot"}

    # 🚀 FIX: Wenn der Server abbricht (IncompleteRead), versuchen wir es bis zu 3x neu!
    for attempt in range(3):
        try:
            with requests.get(url, headers=headers, stream=True, timeout=20) as req:
                req.raise_for_status()
                with open(local_path, "wb") as file_out:
                    shutil.copyfileobj(req.raw, file_out)
            break  # Download erfolgreich -> Schleife beenden
        except Exception as e:
            if attempt < 2:
                time.sleep(2)  # Kurz durchatmen, dann erneuter Versuch
                continue
            raise e  # Beim 3. Versuch endgültig abbrechen und Fehler werfen


def _log_verification_result(fname, sr_status, st_status, sr_details):
    """Hilfsfunktion für das Logging der Ergebnisse."""
    if sr_status == "PASS" and st_status == "PASS":
        log_info(f"   ✅ PASS (Strict & SR): {fname}")
    elif sr_status == "PASS" and st_status == "FAIL":
        log_info(f"   🟡 PASS (SR) / FAIL (Strict): {fname}")
    elif sr_status == "FAIL":
        short = (sr_details[:50] + "..") if len(sr_details) > 50 else sr_details
        log_info(f"   ❌ FAIL (SR): {short}")
    else:
        log_info(f"   ⚠️ ERROR: {sr_details}")


# pylint: disable=too-many-locals
def _process_single_pdf(url, idx, total, temp_dir, verapdf_path):
    """Lädt ein einzelnes PDF und prüft es."""
    fname = os.path.basename(urlparse(url).path) or f"doc_{idx}.pdf"
    lpath = os.path.join(temp_dir, fname)

    log_info(f"[{idx}/{total}] ⏳ Prüfe: {fname}")

    entry = {
        "url": url,
        "filename": fname,
        "status": "UNKNOWN",
        "details": "",
        "profile": "",
        "author": "Unknown",
        "date": "Unknown",
    }

    try:
        _download_file(url, lpath)
        entry.update(_get_pdf_metadata(lpath))

        # 1. Strikter Check
        st_st, st_det, _, timeout_used = _run_verapdf(verapdf_path, lpath)

        # 2. Lockere Prüfung
        if st_st == "ERROR" and "Timeout" in st_det:
            sr_st = "ERROR"
            sr_det = "VeraPDF Timeout (Skipped SR Check)"
            log_warning(f"   ⏩ Überspringe SR-Check: {fname}")
        else:
            sr_st, sr_det, _, _ = _run_verapdf(
                verapdf_path,
                lpath,
                load_config()["active_paths"].get("custom_profile"),
                timeout_used,
            )

        entry.update(
            {
                "status": sr_st,
                "status_strict": st_st,
                "details": sr_det,
                "details_strict": st_det,
                "profile": "ScreenReadable",
            }
        )
        _log_verification_result(fname, sr_st, st_st, sr_det)
    except Exception as err:  # pylint: disable=broad-exception-caught
        entry.update({"status": "ERROR", "details": f"Download/System Fehler: {err}"})
        log_error(f"   Dateifehler ({fname}): {err}")
    finally:
        if os.path.exists(lpath):
            os.remove(lpath)

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
    log_info(f"Starte VeraPDF Prüfung für {len(urls)} Dateien...")

    for i, url in enumerate(urls, 1):
        res = _process_single_pdf(url, i, len(urls), temp_dir, verapdf_path)
        results.append(res)

    # Sortierung: PASS(0) -> FAIL(1) -> Rest(2)
    results.sort(key=lambda x: {"PASS": 0, "FAIL": 1}.get(x["status"], 2))

    with open(output_json, "w", encoding="utf-8") as f_out:
        json.dump(results, f_out, indent=2, ensure_ascii=False)

    timeouts = sum(1 for r in results if "Timeout" in r["details"])
    log_info(f"⏱️ Total Timeouts: {timeouts} of {len(results)}")

    return results
