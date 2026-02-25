import os
import subprocess

from core.utils.error_utils import log_error, log_info


def convert_to_pdfa(input_path, output_path):
    """
    Konvertiert ein PDF in ein technisch sauberes PDF/A-1b mittels Ghostscript.
    Repariert defekte Schriften, Farbräume und Syntaxfehler.
    """
    # Ghostscript Befehl für Linux (gs statt gs.exe)
    cmd = [
        "gs",
        "-dPDFA",
        "-dBATCH",
        "-dNOPAUSE",
        "-dNOOUTERSAVE",
        "-sDEVICE=pdfwrite",
        "-sColorConversionStrategy=RGB",
        "-sProcessColorModel=DeviceRGB",
        f"-sOutputFile={output_path}",
        input_path,
    ]

    try:
        log_info(f"   🛠️ Repariere: {os.path.basename(input_path)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            return True
        else:
            log_error(f"   ❌ GS Fehler: {result.stderr}")
            return False
    except Exception as e:
        log_error(f"   ❌ Konvertierung fehlgeschlagen: {e}")
        return False
