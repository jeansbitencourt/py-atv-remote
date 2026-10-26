#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== Instalando py-atv-remote no ambiente de usuário ==="

# 1. Verificar comando uv
if ! command -v uv &> /dev/null; then
    if [ -f "$HOME/.local/bin/uv" ]; then
        export PATH="$HOME/.local/bin:$PATH"
    else
        echo "Erro: uv não encontrado. Instale com: curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
fi

# 2. Instalar CLI/App globalmente para o usuário via uv tool
echo "→ Compilando e instalando pacote via 'uv tool'..."
uv tool install --force "${PROJECT_ROOT}"

# 3. Criar diretórios de desktop e ícones
APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
mkdir -p "${APPS_DIR}" "${ICONS_DIR}"

# 4. Copiar ícone SVG
echo "→ Instalando ícone do aplicativo..."
cp "${PROJECT_ROOT}/packaging/py-atv-remote.svg" "${ICONS_DIR}/py-atv-remote.svg"

# 5. Copiar atalho .desktop
echo "→ Instalando atalho no menu de aplicativos (.desktop)..."
cp "${PROJECT_ROOT}/packaging/py-atv-remote.desktop" "${APPS_DIR}/py-atv-remote.desktop"

# 6. Atualizar base de dados do desktop se disponível
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "${APPS_DIR}" 2>/dev/null || true
fi

echo ""
echo "✔ Instalação concluída com sucesso!"
echo "O py-atv-remote agora pode ser iniciado:"
echo "  - Pelo menu de aplicativos do KDE/GNOME ('py-atv-remote')"
echo "  - Pelo terminal executando: py-atv-remote"
