"""
Hilfswerkzeuge für Spracherkennung und Übersetzung.
"""

from deep_translator import GoogleTranslator
from langdetect import DetectorFactory, detect

from core.utils.error_utils import log_error, log_info

# Konsistente Ergebnisse sicherstellen
DetectorFactory.seed = 0


def get_document_language(text):
    """
    Erkennt die Hauptsprache eines Textes.
    Gibt ISO-Code (z.B. 'de') zurück.
    """
    if not text or len(text.strip()) < 20:
        return "de"
    try:
        lang = detect(text)
        log_info(f"   🌐 Sprache erkannt: {lang}")
        return lang
    except Exception as err:  # pylint: disable=broad-exception-caught
        log_error(f"   ❌ Fehler bei Spracherkennung: {err}")
        return "de"


def translate_description(text, target_lang):
    """
    Übersetzt Text (primär von BLIP/en) in die Zielsprache.
    """
    if not text or target_lang == "en":
        return text
    try:
        translator = GoogleTranslator(source="en", target=target_lang)
        return translator.translate(text)
    except Exception as err:  # pylint: disable=broad-exception-caught
        log_error(f"   ❌ Fehler Übersetzung fehlgeschlagen: {err}")
        return text
