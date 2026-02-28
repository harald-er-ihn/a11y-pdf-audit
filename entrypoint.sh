#!/usr/bin/env bash
# entrypoint.sh

# Verzeichnis sicherstellen
mkdir -p /data

# Erstelle Swap auf dem persistenten Volume, falls nicht vorhanden
if [ ! -f /data/swapfile ]; then
    echo "Creating 2G Swapfile on Volume /data..."
    # Prüfe ob genug Platz da ist, bevor wir fallocate nutzen
    fallocate -l 2G /data/swapfile 2>/dev/null || dd if=/dev/zero of=/data/swapfile bs=1M count=2048
    chmod 600 /data/swapfile
    mkswap /data/swapfile
fi

# Swap aktivieren (ignoriere Fehler lokal/ohne Privilegien)
swapon /data/swapfile 2>/dev/null && echo "✅ Swap enabled." || echo "⚠️ Swap skipped (local or no permission)."

echo "🚀 Starting App..."
exec "$@"
