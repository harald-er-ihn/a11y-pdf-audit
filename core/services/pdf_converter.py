import argparse
import os
import subprocess

import pikepdf
import psutil

from core.utils.error_utils import log_error, log_info, log_warning
from core.utils.image_captioning import get_image_description
from core.utils.lang_utils import get_document_language, translate_description

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


def fix_technical(input_path, output_path):
    """Klassische technische Reparatur via Ghostscript."""
    # Ghostscript Parameter zur technischen Sanierung nach PDF/A-1b
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
        if not __name__ == "__main__":  # Im CLI wollen wir print nutzen
            log_error(f"   ❌ Ghostscript Fehler: {e}")
        return False


def improve_with_marker(input_path, output_path):
    try:
        models = load_all_models()
        full_text, images, _ = convert_single_pdf(input_path, models)

        # --- NEU: Sprache erkennen ---
        doc_lang = get_document_language(full_text)

        # 2. Bilder mit BLIP beschreiben UND übersetzen
        for img_name, img_data in images.items():
            en_description = get_image_description(img_data)

            # --- NEU: Beschreibung übersetzen ---
            final_description = translate_description(en_description, doc_lang)
            log_info(f"   🖼️ Bild: {final_description} ({doc_lang})")

            temp_img_path = os.path.join(os.path.dirname(output_path), img_name)
            img_data.save(temp_img_path)

            full_text = full_text.replace(
                f"[{img_name}]",
                f'<img src="file://{temp_img_path}" alt="{final_description}">',
            )

        # 3. HTML bauen (mit dynamischer Sprache)
        html_content = f"""
        <!DOCTYPE html>
        <html lang="{doc_lang}"> 
        <head>
            <meta charset="UTF-8">
            <style>body {{ font-family: DejaVu Sans, sans-serif; }}</style>
        </head>
        <body>{full_text}</body>
        </html>
        """

        # 4. WeasyPrint
        HTML(string=html_content).write_pdf(output_path, pdf_variant="pdf/ua-1")

        # 5. Metadaten-Fix (Pikepdf)
        with pikepdf.open(output_path, allow_overwriting_input=True) as pdf:
            # WICHTIG für VeraPDF: Sprache im Root-Level setzen!
            pdf.Root.Lang = pikepdf.String(doc_lang)

            # Tab-Order & DisplayDocTitle (wie gehabt)
            for page in pdf.pages:
                page.Tabs = pikepdf.Name("/S")
            pdf.Root.ViewerPreferences = pikepdf.Dictionary(DisplayDocTitle=True)
            pdf.save(output_path)

        return True
    except Exception as e:
        log_error(f"   ❌ Fehler: {e}")
        return False


def run_improvement(input_path, output_path, force_ai=False):
    """Entscheidungslogik zwischen GS und Marker."""
    if not os.path.exists(input_path):
        return False

    total_ram = psutil.virtual_memory().total / (1024**3)
    on_fly = is_on_fly()

    # KI Modus nur wenn lokal, genug RAM und Libs vorhanden
    if force_ai and not on_fly and total_ram >= 4 and HAS_AI_LIBS:
        return improve_with_marker(input_path, output_path)
    else:
        return fix_technical(input_path, output_path)


# --- CLI INTERFACE ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PDF A11y Auditor - Converter CLI")
    parser.add_argument("input", help="Pfad zum Quell-PDF")
    parser.add_argument("output", help="Pfad zum Ziel-PDF")
    parser.add_argument(
        "--ai",
        action="store_true",
        help="Nutze Marker AI für Rekonstruktion (benötigt viel RAM)",
    )

    args = parser.parse_args()

    print(f"🚀 Starte Konvertierung: {args.input}")

    success = run_improvement(args.input, args.output, force_ai=args.ai)

    if success:
        print(f"✅ Erfolg! Datei gespeichert unter: {args.output}")
        # Kleiner Bonus: Direkt VeraPDF Check vorschlagen
        print(f"Tipp: Prüfe die Datei mit: verapdf --format text {args.output}")
    else:
        print(f"❌ Fehler bei der Konvertierung von {args.input}")
