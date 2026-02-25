import os
import zipfile

from core.utils.error_utils import log_info


def create_repair_zip(pdf_files, zip_output_path):
    """
    Packt alle erfolgreich konvertierten Dateien in eine ZIP.
    pdf_files: Liste von absoluten Pfaden
    """
    if not pdf_files:
        return None

    log_info(f"   📦 Erstelle ZIP: {len(pdf_files)} Dateien...")
    with zipfile.ZipFile(zip_output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file in pdf_files:
            if os.path.exists(file):
                # Speichere Datei im ZIP ohne den kompletten Pfad
                zipf.write(file, os.path.basename(file))

    return zip_output_path
