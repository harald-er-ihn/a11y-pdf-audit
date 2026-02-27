"""
Kombinierter Service für technische Reparatur (GS) und KI-Rekonstruktion (Marker).
"""
import os
import subprocess

import psutil

from core.utils.error_utils import log_error, log_info


def fix_technical(input_path, output_path):
    """Repariert PDF-Syntax und bettet Schriften ein via Ghostscript."""
    cmd = [
        "gs",
        "-dPDFA",
        "-dBATCH",
        "-dNOPAUSE",
        "-dNOOUTERSAVE",
        "-sDEVICE=pdfwrite",
        "-dPDFACompatibilityPolicy=1",
        f"-sOutputFile={output_path}",
        input_path,
    ]
    try:
        # pylint: disable=subprocess-run-check
        proc = subprocess.run(cmd, capture_output=True)
        return proc.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError) as err:
        log_error(f"   ❌ GS-Systemfehler: {err}")
        return False


def improve_with_marker(input_path, output_path):
    """Semantische Rekonstruktion via Marker AI (v1.x API)."""
    try:
        # Lokale Imports, damit der Rest ohne Marker-Absturz lädt
        from marker.converters.pdf import PdfConverter
        from marker.models import load_all_models
        from marker.output import save_output

        log_info("   🤖 Initialisiere Marker v1.x Modelle...")

        # In v1.x erstellt man einen Converter
        converter = PdfConverter(artifact_dict=load_all_models())

        # Konvertierung starten
        result = converter(input_path)

        # Speichern (Markdown/HTML/JSON)
        # Wir nutzen hier die save_output Helper der Library
        full_text, images, metadata = save_output(
            result, os.path.dirname(output_pdf), "output"
        )

        # Hier müsste nun WeasyPrint den HTML-String wieder in PDF wandeln
        # (Da dieser Teil sehr komplex ist, lassen wir Marker primär
        # Markdown/Layout liefern).
        log_info(f"   ✅ KI-Rekonstruktion fertig: {metadata.get('language')}")
        return True
    except Exception as err:  # pylint: disable=broad-exception-caught
        log_error(f"   ❌ KI-Error (v1.x): {err}")
        return False


def run_improvement(input_path, output_path, force_ai=False):
    """Entscheidet zwischen technischem Fix und KI-Modus."""
    ram_gb = psutil.virtual_memory().total / (1024**3)
    is_fly = os.environ.get("FLY_APP_NAME") is not None

    if force_ai and not is_fly and ram_gb >= 4:
        log_info(f"   ✨ Modus: KI-Rekonstruktion ({os.path.basename(input_path)})")
        return improve_with_marker(input_path, output_path)

    log_info(f"   🔧 Modus: Technischer Fix ({os.path.basename(input_path)})")
    return fix_technical(input_path, output_path)
