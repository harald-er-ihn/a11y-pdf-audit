"""
Hilfswerkzeuge für Spracherkennung und Übersetzung.
"""

from core.utils.error_utils import log_error, log_info


def get_document_language(text):
    """
    Erkennt die Hauptsprache eines Textes.
    Gibt ISO-Code (z.B. 'de') zurück.
    """
    try:
        from langdetect import DetectorFactory, detect

        # Sorgt für konsistente Ergebnisse bei kurzen Texten
        DetectorFactory.seed = 0
        if not text or len(text.strip()) < 20:
            return "de"
        lang = detect(text)
        log_info(f"   🌐 Sprache erkannt: {lang}")
        return lang
    except Exception as err:
        log_error(f"   ❌ Fehler bei Spracherkennung: {err}")
        return "de"


def translate_description(text, target_lang):
    """
    Übersetzt Text (primär von BLIP/en) in die Zielsprache.
    """
    if not text or target_lang == "en":
        return text
    try:
        from deep_translator import GoogleTranslator

        # GoogleTranslator ist für A11y Alt-Texte sehr zuverlässig
        translator = GoogleTranslator(source="en", target=target_lang)
        log_info(f"   🌐 bersetzt die BLIP-Beschreibung in: {target_lang}")
        return translator.translate(text)
    except Exception as err:
        log_error(f"   ❌ Fehler Übersetzung fehlgeschlagen: {err}")
        return text  # Fallback auf das englische Original
