"""
Zentrale Hilfsfunktionen für Logging und Fehlerbehandlung.
"""

import logging
import os
import sys

# Logger-Instanz holen
logger = logging.getLogger("a11y-audit")


def setup_logging(log_dir=None):
    """
    Konfiguriert das Logging.
    Ausgaben landen in stdout (für Docker) UND optional in einer Datei.
    """
    handlers = [logging.StreamHandler(sys.stdout)]

    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        # Immer 'audit.log' verwenden
        file_handler = logging.FileHandler(
            os.path.join(log_dir, "audit.log"), encoding="utf-8"
        )
        handlers.append(file_handler)

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        handlers=handlers,
        force=True,
    )


def log_info(msg):
    """Loggt eine Info-Nachricht."""
    logger.info(msg)


def log_error(msg):
    """Loggt eine Fehler-Nachricht."""
    logger.error(msg)


def log_warning(msg):
    """Loggt eine Warnung."""
    logger.warning(msg)
