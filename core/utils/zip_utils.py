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
    used_names = set()  # Zum Tracken von Duplikaten

    with zipfile.ZipFile(zip_output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for idx, file in enumerate(pdf_files):
            if os.path.exists(file):
                base_name = os.path.basename(file)
                # Wenn Name schon existiert, Index anhängen
                if base_name in used_names:
                    base_name = f"{idx}_{base_name}"
                used_names.add(base_name)
                # Speichere Datei im ZIP ohne den kompletten Pfad
                zipf.write(file, base_name)
    return zip_output_path
