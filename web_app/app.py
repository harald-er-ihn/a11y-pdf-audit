"""
Einstiegspunkt für die Flask-Webanwendung.
Stellt die 'app' Instanz für Gunicorn bereit und setzt Security Header.
"""

import os

from flask import Flask

from core.utils.config_loader import load_config
from web_app.routes_main import main_bp


def create_app():
    """
    Erstellt und konfiguriert die Flask-App.
    """
    flask_app = Flask(
        __name__, template_folder="../templates", static_folder="../static"
    )
    flask_app.register_blueprint(main_bp)

    # Globale Variable 'config' für alle Templates verfügbar machen
    @flask_app.context_processor
    def inject_config():
        return dict(config=load_config())

    # --- SECURITY HEADERS (Fix für Screaming Frog "Sicherheit") ---
    @flask_app.after_request
    def add_security_headers(response):
        # Schutz vor Clickjacking
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        # Schutz vor MIME-Type Sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # HSTS (Erzwingt HTTPS) - 1 Jahr
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Content Security Policy (CSP) - Erlaubt Skripte/Styles von uns selbst (und Inline, da wir JS im Template haben)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' https://www.paypal.com;"
        )

        return response

    return flask_app


# WICHTIG: Globale Instanz für Gunicorn
app = create_app()

if __name__ == "__main__":
    DEBUG_MODE = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    PORT = int(os.environ.get("FLASK_PORT", 8000))
    HOST = os.environ.get("FLASK_HOST", "0.0.0.0")  # nosec B104

    app.run(debug=DEBUG_MODE, port=PORT, host=HOST)
