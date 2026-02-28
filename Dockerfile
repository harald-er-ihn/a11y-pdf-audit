# ------------------------------------------------------------
# 🧩 a11y-pdf-audit - Fix für Python 3.12 (pkg_resources)
# ------------------------------------------------------------
FROM python:3.12-slim

# 1. System-Umgebung konfigurieren
ENV PYTHONPATH="/app" \
    TZ=Europe/Berlin \
    FLASK_HOST=0.0.0.0 \
    FLASK_PORT=8000 \
    MARKER_CACHE_DIR=/app/models_cache \
    HF_HOME=/app/models_cache \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN mkdir -p /data /app/output

# 2. System-Abhängigkeiten
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
        build-essential \
        gcc && \
    ln -fs /usr/share/zoneinfo/Europe/Berlin /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 3. Python-Abhängigkeiten
COPY requirements.txt .

RUN python -m pip install --upgrade pip && \
    # Torch-CPU zuerst (spart Platz)
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    # Dann alle Requirements
    pip install --no-cache-dir -r requirements.txt && \
    # EXTREM WICHTIG: setuptools AM ENDE installieren, damit pkg_resources garantiert da ist
    pip install --no-cache-dir setuptools==70.0.0 wheel && \
    # Cleanup
    apt-get purge -y --auto-remove build-essential gcc

# 4. App-Code & VeraPDF
RUN mkdir -p /app/models_cache && mkdir -p /opt/verapdf
COPY verapdf_local/bin/greenfield-apps-1.28.2.jar /opt/verapdf/veraPDF-cli.jar
COPY . .

EXPOSE 8000

# 4.b Entrypoint für swap-Space 2G
RUN chmod +x entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]



# 5. Start (Geändert auf "python3 -m gunicorn" um Pfad-Probleme zu umgehen)
CMD ["python3", "-m", "gunicorn", "web_app.app:app", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "1", \
     "--timeout", "600", \
     "--log-level", "debug"]
