# ------------------------------------------------------------
# 🧩 a11y-pdf-audit - Optimiert für Marker AI & WeasyPrint
# ------------------------------------------------------------
FROM python:3.12-slim

# 1. System-Umgebung konfigurieren
ENV PYTHONPATH="/app" \
    TZ=Europe/Berlin \
    FLASK_HOST=0.0.0.0 \
    FLASK_PORT=8000 \
    # Marker/Huggingface Cache-Ordner festlegen
    MARKER_CACHE_DIR=/app/models_cache \
    HF_HOME=/app/models_cache \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 2. System-Abhängigkeiten (Kombiniert für weniger Layer)
# Headless JRE für VeraPDF, Pango/Cairo für WeasyPrint, GS für Fixes
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ghostscript \
        default-jre-headless \
        curl \
        libpangocairo-1.0-0 \
        libharfbuzz0b \
        libpangoft2-1.0-0 \
        libffi-dev \
        libxml2-dev \
        libxslt1-dev \
        fonts-dejavu-core \
        fonts-liberation \
        tzdata \
        # Build-Tools (nur für die Installation benötigt)
        build-essential \
        gcc && \
    # Zeitzone setzen
    ln -fs /usr/share/zoneinfo/Europe/Berlin /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 3. Python-Abhängigkeiten intelligent installieren
COPY requirements.txt .

RUN python -m pip install --upgrade pip setuptools wheel && \
    # Erst Torch-CPU (spart GB-weise NVIDIA-Treiber im Image)
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    # Dann den Rest der Requirements
    pip install --no-cache-dir -r requirements.txt && \
    # Build-Tools wieder entfernen, um Image klein zu halten (Optional)
    apt-get purge -y --auto-remove build-essential gcc

# 4. VeraPDF & Code kopieren
# Erstelle Cache-Ordner vorab
RUN mkdir -p /app/models_cache && mkdir -p /opt/verapdf

COPY verapdf_local/bin/greenfield-apps-1.28.2.jar /opt/verapdf/veraPDF-cli.jar
COPY . .

EXPOSE 8000

# 5. Start-Konfiguration
# Workers=1 ist bei KI-Modellen (Marker) Pflicht, sonst explodiert der RAM
CMD ["gunicorn", "web_app.app:app", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "1", \
     "--timeout", "600", \
     "--access-log-file", "-", \
     "--error-log-file", "-"]
