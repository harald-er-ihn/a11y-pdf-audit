import os
import subprocess

import psutil

from core.utils.error_utils import log_error, log_info, log_warning

# Marker-Import mit Fallback
try:
    from marker.convert import convert_single_pdf
    from marker.models import load_all_models
    from weasyprint import HTML

    HAS_AI_LIBS = True
except ImportError:
    HAS_AI_LIBS = False


def has_enough_ram(min_gb=4):
    """Prüft, ob das System mindestens min_gb Arbeitsspeicher hat."""
    total_ram = psutil.virtual_memory().total / (1024**3)
    return total_ram >= min_gb


def is_on_fly():
    """Prüft, ob die App auf Fly.io läuft."""
    return os.environ.get("FLY_APP_NAME") is not None


def convert_to_pdfa_technical(input_path, output_path):
    """Klassische technische Reparatur via Ghostscript (v1.3 Standard)."""
    cmd = [
        "gs",
        "-dPDFA",
        "-dBATCH",
        "-dNOPAUSE",
        "-dNOOUTERSAVE",
        "-sDEVICE=pdfwrite",
        "-dPDFACompatibilityPolicy=1",
        "-sColorConversionStrategy=RGB",
        "-sProcessColorModel=DeviceRGB",
        f"-sOutputFile={output_path}",
        input_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return result.returncode == 0 and os.path.exists(output_path)
    except Exception as e:
        log_error(f"   ❌ Ghostscript Fehler: {e}")
        return False


def improve_with_marker(input_path, output_path):
    """Semantische Rekonstruktion via Marker."""
    try:
        models = load_all_models()
        full_text, _, _ = convert_single_pdf(input_path, models)
        HTML(string=f"<html><body>{full_text}</body></html>").write_pdf(
            output_path, pdf_variant="pdf/ua-1"
        )
        return True
    except Exception as e:
        log_error(f"Marker Error: {e}")
        return False


def fix_technical(input_path, output_path):
    """Technische Rekonstruktion via Ghostscript."""
    cmd = [
        "gs",
        "-dPDFA",
        "-dBATCH",
        "-dNOPAUSE",
        "-dNOOUTERSAVE",
        "-sDEVICE=pdfwrite",
        "-dPDFACompatibilityPolicy=1",
        "-sOutputFile=" + output_path,
        input_path,
    ]
    return subprocess.run(cmd, capture_output=True).returncode == 0


def improve_pdf_with_ai(input_path, output_path):
    """Semantische Rekonstruktion via Marker AI (v1.3 High-End)."""
    if not HAS_AI_LIBS:
        log_error("   ❌ KI-Bibliotheken (Marker/Torch) nicht installiert.")
        return False

    try:
        log_info(f"   🤖 KI-Modelle werden geladen (Marker)...")
        models = load_all_models()
        # PDF -> Markdown/HTML Struktur
        full_text, images, out_meta = convert_single_pdf(input_path, models)

        # Das Ergebnis (Markdown/HTML) via WeasyPrint als PDF/UA neu aufbauen
        # (Einfacher Wrapper um den Text für dieses Beispiel)
        html_content = f"<html><body>{full_text}</body></html>"
        HTML(string=html_content).write_pdf(output_path, pdf_variant="pdf/ua-1")
        return True
    except Exception as e:
        log_error(f"   ❌ Marker AI Fehler: {e}")
        return False


def run_improvement(input_path, output_path, force_ai=False):
    """
    Hauptfunktion: Entscheidet zwischen technischem Fix und KI-Rekonstruktion.
    """
    total_ram = psutil.virtual_memory().total / (1024**3)
    on_fly = os.environ.get("FLY_APP_NAME") is not None

    if force_ai and not on_fly and total_ram >= 4 and HAS_AI_LIBS:
        log_info(f"   ✨ Modus: AI-Rekonstruktion (Marker)")
        return improve_with_marker(input_path, output_path)
    else:
        log_info(f"   🔧 Modus: Technischer Fix (Ghostscript)")
        return fix_technical(input_path, output_path)
