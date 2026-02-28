"""
Service zur automatischen Beschreibung von Bildern (Image Captioning).
"""

from core.utils.error_utils import log_error, log_info

# Globale Instanzen für Lazy-Loading
_PROCESSOR = None
_MODEL = None


def _initialize_blip():
    """Initialisiert das BLIP-Modell einmalig."""
    global _PROCESSOR, _MODEL
    if _MODEL is None:
        import torch
        from transformers import BlipForConditionalGeneration, BlipProcessor

        model_id = "Salesforce/blip-image-captioning-base"
        log_info(f"   🤖 Lade Vision-Modell: {model_id}")

        _PROCESSOR = BlipProcessor.from_pretrained(model_id)
        # Fix Deprecation: Wir nutzen kein 'device' Argument in from_pretrained
        _MODEL = BlipForConditionalGeneration.from_pretrained(model_id)

        # Auf CPU schalten (für Docker/Standard-Server)
        _MODEL.to("cpu")
    return _PROCESSOR, _MODEL


def get_image_description(pil_image):
    """Generiert eine Textbeschreibung für ein PIL-Bild."""
    try:
        processor, model = _initialize_blip()

        # Vorbereitung der Inputs
        inputs = processor(pil_image, return_tensors="pt")

        # Generierung ohne Deprecated 'device' Argument
        out = model.generate(**inputs, max_new_tokens=40)
        description = processor.decode(out[0], skip_special_tokens=True)

        return description.capitalize()
    except Exception as err:
        log_error(f"   ❌ BLIP-Fehler: {err}")
        return "Visual representation"


def load_blip():
    """Lädt Transformers erst beim ersten echten Aufruf."""
    global _PROCESSOR, _MODEL
    if _MODEL is None:
        # INTERNE IMPORTS - Versteckt vor Gunicorn
        import torch
        from transformers import BlipForConditionalGeneration, BlipProcessor

        log_info("   🤖 Lade BLIP Vision-Modell (Lazy Load)...")
        model_id = "Salesforce/blip-image-captioning-base"
        _PROCESSOR = BlipProcessor.from_pretrained(model_id)
        _MODEL = BlipForConditionalGeneration.from_pretrained(model_id)
    return _PROCESSOR, _MODEL
