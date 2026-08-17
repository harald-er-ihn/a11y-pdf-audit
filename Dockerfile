FROM python:3.12-slim

ENV PYTHONPATH="/app" \
    TZ=Europe/Berlin \
    FLASK_HOST=0.0.0.0 \
    FLASK_PORT=8000 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN mkdir -p /data /app/output

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
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
        fontconfig \
        tzdata \
        build-essential \
        gcc && \
    ln -fs /usr/share/zoneinfo/Europe/Berlin /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get purge -y --auto-remove build-essential gcc

RUN mkdir -p /opt/verapdf
COPY verapdf_local/bin/greenfield-apps-1.28.2.jar /opt/verapdf/veraPDF-cli.jar
COPY . .

EXPOSE 8000

RUN chmod +x entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]

CMD ["python3", "-m", "gunicorn", "web_app.app:app", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--timeout", "120", \
     "--log-level", "info"]
