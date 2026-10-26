#!/usr/bin/env bash
set -euo pipefail

echo "=== Desinstalando atalhos do py-atv-remote ==="

APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"

rm -f "${APPS_DIR}/py-atv-remote.desktop"
rm -f "${ICONS_DIR}/py-atv-remote.svg"

if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "${APPS_DIR}" 2>/dev/null || true
fi

if command -v uv &> /dev/null; then
    uv tool uninstall py-atv-remote 2>/dev/null || true
fi

echo "✔ Desinstalação concluída."
