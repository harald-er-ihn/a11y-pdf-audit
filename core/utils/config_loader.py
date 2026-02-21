"""
Lädt die Konfiguration aus der JSON-Datei.
"""

import json
import os


def load_config():
    """
    Lädt config.json und bestimmt aktive Pfade basierend auf der Umgebung.
    """
    base_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    config_path = os.path.join(base_dir, "config", "config.json")

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Automatische Erkennung ob Fly.io oder Lokal
    if os.environ.get("FLY_APP_NAME"):
        config["active_paths"] = {
            "output": config["paths"]["output_dir_fly"],
            "verapdf": config["paths"]["verapdf_cli_fly"],
        }
    else:
        # Lokal: absolute Pfade relativ zum Projektroot
        config["active_paths"] = {
            "output": os.path.join(base_dir, config["paths"]["output_dir_local"]),
            "verapdf": os.path.join(base_dir, config["paths"]["verapdf_cli_local"]),
        }

    return config
