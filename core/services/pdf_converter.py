"""
Kombinierter Service für technische Reparatur (GS) und KI-Rekonstruktion (Marker).
"""
import argparse
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
        proc = subprocess.run(cmd, capture_output=True, check=False)
        return proc.returncode == 0
    except Exception as err:
        log_error(f"   ❌ GS-Systemfehler: {err}")
        return False


def _process_ai_images(images, output_dir, doc_lang):
    """Helper: Verarbeitet Bilder mit Vision-KI und gibt Alt-Text Map zurück."""
    from PIL import Image

    from core.utils.image_captioning import get_image_description
    from core.utils.lang_utils import translate_description

    alt_map = {}
    for img_name, img_data in images.items():
        # Falls Marker Pfade liefert, Bild laden
        img_obj = Image.open(img_data) if isinstance(img_data, str) else img_data

        # KI-Beschreibung
        en_desc = get_image_description(img_obj)
        final_desc = translate_description(en_desc, doc_lang)

        # Speichern für WeasyPrint
        target_path = os.path.join(output_dir, img_name)
        img_obj.save(target_path)
        alt_map[img_name] = (target_path, final_desc)
    return alt_map


def improve_with_marker(input_path, output_path):
    """Semantische Rekonstruktion via Marker AI."""
    try:
        import pikepdf
        from marker.convert import convert_single_pdf
        from marker.models import load_all_models
        from weasyprint import HTML

        from core.utils.lang_utils import get_document_language

        log_info("   🤖 Initialisiere KI-Modelle...")
        # WICHTIG: Marker erwartet Modelle ohne vordefinierte Pfade bei Problemen
        full_text, images, *rest = convert_single_pdf(input_path, load_all_models())

        doc_lang = get_document_language(full_text)
        alt_map = _process_ai_images(images, os.path.dirname(output_path), doc_lang)

        # HTML-Aufbau
        for img_id, (path, desc) in alt_map.items():
            full_text = full_text.replace(
                f"[{img_id}]", f'<img src="file://{path}" alt="{desc}">'
            )

        html = f"<!DOCTYPE html><html lang='{doc_lang}'><body>{full_text}</body></html>"
        HTML(string=html).write_pdf(output_path, pdf_variant="pdf/ua-1")

        # Metadaten-Fix
        with pikepdf.open(output_path, allow_overwriting_input=True) as pdf:
            pdf.Root.Lang = pikepdf.String(doc_lang)
            pdf.Root.ViewerPreferences = pikepdf.Dictionary(DisplayDocTitle=True)
            for page in pdf.pages:
                page.Tabs = pikepdf.Name("/S")
            pdf.save(output_path)
        return True
    except Exception as err:
        log_error(f"   ❌ KI-Error: {err}")
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


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--ai", action="store_true")
    a = p.parse_args()
    run_improvement(a.input, a.output, force_ai=a.ai)
