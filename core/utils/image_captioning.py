import torch
from transformers import BlipForConditionalGeneration, BlipProcessor

from core.utils.error_utils import log_error, log_info

# Globale Variablen für Lazy-Loading
_PROCESSOR = None
_MODEL = None


def load_blip():
    """Lädt Prozessor und Modell nur bei Bedarf (Singleton)."""
    global _PROCESSOR, _MODEL
    if _MODEL is None:
        log_info("   🤖 Lade BLIP Vision-Modell (Salesforce)...")
        model_id = "Salesforce/blip-image-captioning-base"
        _PROCESSOR = BlipProcessor.from_pretrained(model_id)
        # Wir zwingen das Modell auf die CPU (da Docker meist keine GPU hat)
        _MODEL = BlipForConditionalGeneration.from_pretrained(model_id)
    return _PROCESSOR, _MODEL


def get_image_description(pil_image):
    """Generiert eine englische Beschreibung für ein PIL-Image Objekt."""
    try:
        processor, model = load_blip()

        # Bild für die KI vorbereiten
        inputs = processor(pil_image, return_tensors="pt")

        # Beschreibung generieren
        out = model.generate(**inputs, max_new_tokens=50)
        description = processor.decode(out[0], skip_special_tokens=True)

        return description.capitalize()
    except Exception as e:
        log_error(f"   ❌ BLIP Fehler: {e}")
        return "Visual representation or graphic"  # Fallback
