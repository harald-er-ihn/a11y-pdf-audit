# ------------------------------------------------------------
# 🧩 a11y-pdf-audit - minimal, zuverlässig
# ------------------------------------------------------------
FROM python:3.12-slim

WORKDIR /app

# Kopiere requirements zuerst (Cache nutzen)
COPY requirements.txt /app/requirements.txt

# Systempakete inkl. Java, Zeitzone, etc.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ghostscript \
        default-jre \
        curl \
        unzip \
        libcairo2 \
        libpango-1.0-0 \
        libgdk-pixbuf-xlib-2.0-0 \
        libffi8 \
        libglib2.0-0 \
        fonts-dejavu-core \
        build-essential \
        python3-dev \
        python3-setuptools \
        python3-pkg-resources \
        libxml2-dev \
        libxslt1-dev \
        zlib1g-dev \
        gcc \
        tzdata && \
    # Zeitzone setzen
    ln -fs /usr/share/zoneinfo/Europe/Berlin /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata && \
    python -m pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /app/requirements.txt && \
    rm -rf /var/lib/apt/lists/*

# Rest des Projekts kopieren
COPY . /app

# VeraPDF CLI ins Container-Verzeichnis kopieren
COPY verapdf_local/bin/greenfield-apps-1.28.2.jar /opt/verapdf/veraPDF-cli.jar

ENV FLASK_HOST=0.0.0.0
ENV FLASK_PORT=8000
ENV FLASK_DEBUG=False
ENV PYTHONPATH="/usr/lib/python3/dist-packages:/usr/local/lib/python3.12/site-packages"
# Zeitzone für Python erzwingen
ENV TZ=Europe/Berlin

EXPOSE 8000

# ÄNDERUNG: --workers auf 1 gesetzt
CMD ["gunicorn", "web_app.app:app", "--bind", "0.0.0.0:8000", "--workers", "1", "--timeout", "120"]
