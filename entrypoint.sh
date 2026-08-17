#!/usr/bin/env bash
set -euo pipefail

mkdir -p /a11y_data/output /a11y_data/fonts

SWAP_FILE="/a11y_data/swapfile"
if [ ! -f "$SWAP_FILE" ]; then
    echo "Creating 2G Swapfile for safety..."
    fallocate -l 2G "$SWAP_FILE" 2>/dev/null || dd if=/dev/zero of="$SWAP_FILE" bs=1M count=2048
    chmod 600 "$SWAP_FILE"
    mkswap "$SWAP_FILE"
fi
swapon "$SWAP_FILE" 2>/dev/null && echo "✅ 2GB Swap enabled." || echo "⚠️ Swap skipped."

echo "🚀 Starte Webserver..."
exec "$@"
