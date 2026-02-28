"""
Kombinierter Service für technische Reparatur (Ghostscript)
und KI-Rekonstruktion (Marker + WeasyPrint + GS-Postprocessing).
"""

import argparse
import base64
import builtins
import io
import os
import subprocess
import sys

import psutil

# Pfad-Hack für lokale Module
# pylint: disable=wrong-import-position
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.utils.error_utils import log_error, log_info


def fix_technical(input_path, output_path):
    """Repariert PDF-Syntax und erzwingt PDF/A via Ghostscript."""
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
        # pylint: disable=subprocess-run-check
        proc = subprocess.run(cmd, capture_output=True, check=False)
        return proc.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError) as err:
        log_error(f"   ❌ GS-Systemfehler: {err}")
        return False


def improve_with_marker(input_path, output_path):
    """KI-Rekonstruktion inklusive Logo-Extraktion und PDF/A-Veredelung."""
    # pylint: disable=too-many-locals
    try:
        # pylint: disable=import-outside-toplevel, no-name-in-module
        import markdown
        from marker import models as marker_models
        from marker.converters.pdf import PdfConverter
        from surya.settings import settings as surya_settings
        from weasyprint import HTML

        if not hasattr(builtins, "SPECIAL_TOKENS"):
            setattr(builtins, "SPECIAL_TOKENS", [])

        # Offline-Pfade konfigurieren
        base = os.environ.get("SURYA_CACHE_DIR", os.path.expanduser("~/.cache/surya"))
        map_cfg = {
            "layout": ("2025_09_23", ["LAYOUT_MODEL_CHECKPOINT"]),
            "text_recognition": ("2025_09_23", ["RECOGNITION_MODEL_CHECKPOINT"]),
            "text_detection": ("2025_05_07", ["DETECTION_MODEL_CHECKPOINT"]),
            "table_recognition": ("2025_02_18", ["TABLE_MODEL_CHECKPOINT"]),
            "ocr_error_detection": ("2025_02_18", ["OCR_ERR_MODEL_CHECKPOINT"]),
        }
        for m_t, (ver, keys) in map_cfg.items():
            m_p = os.path.join(base, m_t, ver)
            if os.path.exists(os.path.join(m_p, "model.safetensors")):
                for k in keys:
                    if hasattr(surya_settings, k):
                        setattr(surya_settings, k, m_p)

        log_info(f"   🤖 Initialisiere Marker (Offline: {base})...")
        loader = next(
            (
                getattr(marker_models, n)
                for n in ["create_model_dict", "load_models"]
                if hasattr(marker_models, n)
            ),
            None,
        )
        if not loader:
            raise ImportError("Marker Loader fehlt.")

        conv = PdfConverter(artifact_dict=loader())
        res = conv(input_path)

        # 1. Schritt: Markdown zu HTML konvertieren
        html_body = markdown.markdown(res.markdown, extensions=["tables"])

        # 2. Schritt: Bilder (Logos) einbetten
        # Marker liefert Bilder in res.images als {filename: PIL_Image}
        for img_name, pil_img in res.images.items():
            buffered = io.BytesIO()
            pil_img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            # Ersetze Platzhalter im HTML durch Base64-Data-URI
            html_body = html_body.replace(img_name, f"data:image/png;base64,{img_str}")

        html_content = f"""
        <html><body>
            <style>
                body {{ font-family: sans-serif; padding: 2cm; line-height: 1.5; }}
                img {{ max-width: 300px; display: block; margin-bottom: 1em; }}
                table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
                td, th {{ border: 1px solid #ccc; padding: 8px; }}
            </style>
            {html_body}
        </body></html>
        """

        tmp_pdf = output_path + ".tmp.pdf"
        log_info("   📄 Erzeuge Layout inkl. eingebetteter Grafiken...")
        HTML(string=html_content).write_pdf(tmp_pdf)

        log_info("   🔧 Veredle PDF/A Konformität...")
        success = fix_technical(tmp_pdf, output_path)

        if os.path.exists(tmp_pdf):
            os.remove(tmp_pdf)

        log_info(f"   ✅ Rekonstruktion abgeschlossen: {output_path}")
        return success

    except Exception as err:  # pylint: disable=broad-exception-caught
        log_error(f"   ❌ KI-Fehler: {err}")
        return False


def run_improvement(input_path, output_path, force_ai=False):
    """Entscheidet zwischen technischem Fix und KI-Modus."""
    ram_gb = psutil.virtual_memory().total / (1024**3)
    if force_ai and ram_gb >= 4:
        log_info(f"   ✨ Modus: KI-Rekonstruktion ({os.path.basename(input_path)})")
        return improve_with_marker(input_path, output_path)
    log_info(f"   🔧 Modus: Technischer Fix ({os.path.basename(input_path)})")
    return fix_technical(input_path, output_path)


def main():
    """CLI Einstiegspunkt."""
    parser = argparse.ArgumentParser(description="PDF Reparatur Service")
    parser.add_argument("input", help="Pfad zur Eingabe-PDF")
    parser.add_argument("output", help="Pfad zur Ausgabe-PDF")
    parser.add_argument("--ai", action="store_true", help="KI-Modus erzwingen")
    args = parser.parse_args()
    if not os.path.exists(args.input):
        log_error(f"Datei nicht gefunden: {args.input}")
        sys.exit(1)
    success = run_improvement(args.input, args.output, force_ai=args.ai)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
