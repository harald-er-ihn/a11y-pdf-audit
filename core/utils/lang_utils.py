from deep_translator import GoogleTranslator
from langdetect import DetectorFactory, detect

from core.utils.error_utils import log_error, log_info

# Sorgt für konsistente Ergebnisse bei kurzen Texten
DetectorFactory.seed = 0


def get_document_language(text):
    """Erkennt die Hauptsprache des Textes (z.B. 'de' oder 'en')."""
    try:
        if not text or len(text.strip()) < 10:
            return "de"  # Fallback auf Deutsch
        lang = detect(text)
        log_info(f"   🌐 Sprache erkannt: {lang}")
        return lang
    except Exception as e:
        log_error(f"   ❌ Fehler bei Spracherkennung: {e}")
        return "de"


def translate_description(text, target_lang):
    """Übersetzt die BLIP-Beschreibung in die Zielsprache."""
    try:
        # BLIP liefert immer Englisch
        if target_lang == "en":
            return text

        translated = GoogleTranslator(source="en", target=target_lang).translate(text)
        return translated
    except Exception as e:
        log_error(f"   ⚠️ Übersetzung fehlgeschlagen: {e}")
        return text  # Fallback auf das englische Original
