#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

usage() {
    cat <<'HELP'
Uso: ./scripts/install-desktop.sh [--without-preview | --archive ARQUIVO | WHEEL]

Sem argumentos: prepara ADB/scrcpy verificados, gera o pacote e instala no usuário.
  --without-preview  Instala o controle sem incluir ferramentas de visualização.
  --archive ARQUIVO  Usa um release scrcpy já baixado (SHA-256 obrigatório).
  WHEEL             Instala diretamente um pacote .whl existente.
  --help            Exibe esta ajuda.

Requer Linux com desktop e bibliotecas básicas compatíveis. Ferramentas incluídas
somente em Linux x86_64. Não use sudo. Internet necessária na primeira instalação.
HELP
}

INSTALL_MODE="bundled"
PREVIEW_ARCHIVE=""
INSTALL_WHEEL=""
case "${1:-}" in
    --help|-h) usage; exit 0 ;;
    --without-preview) INSTALL_MODE="plain"; shift ;;
    --archive)
        if [[ $# -lt 2 ]]; then usage >&2; exit 2; fi
        PREVIEW_ARCHIVE="$2"
        shift 2
        ;;
    "") ;;
    -* ) usage >&2; exit 2 ;;
    *) INSTALL_MODE="wheel"; INSTALL_WHEEL="$1"; shift ;;
esac
if [[ $# -ne 0 ]]; then usage >&2; exit 2; fi
if [[ "$(uname -s)" != "Linux" ]]; then
    echo "Erro: este instalador é destinado ao Linux." >&2
    exit 1
fi
if [[ "$INSTALL_MODE" == "bundled" && "$(uname -m)" != "x86_64" ]]; then
    echo "Erro: ADB/scrcpy incluídos disponíveis somente para Linux x86_64." >&2
    echo "Para instalar apenas o controle, use --without-preview." >&2
    exit 1
fi
if [[ "$INSTALL_MODE" == "wheel" && (! -f "$INSTALL_WHEEL" || "$INSTALL_WHEEL" != *.whl) ]]; then
    echo "Erro: informe um arquivo .whl existente." >&2
    exit 2
fi
if [[ -n "$PREVIEW_ARCHIVE" && ! -f "$PREVIEW_ARCHIVE" ]]; then
    echo "Erro: arquivo scrcpy não encontrado." >&2
    exit 2
fi

INSTALL_TEMP="$(mktemp -d)"
trap 'rm -rf -- "$INSTALL_TEMP"' EXIT

echo "=== Instalando py-atv-remote no ambiente de usuário ==="
if ! command -v uv >/dev/null 2>&1; then
    if [[ -x "$HOME/.local/bin/uv" ]]; then
        export PATH="$HOME/.local/bin:$PATH"
    else
        echo "→ Instalando uv pelo instalador oficial..."
        if command -v curl >/dev/null 2>&1; then
            curl --fail --location --proto '=https' --tlsv1.2 \
                https://astral.sh/uv/install.sh -o "$INSTALL_TEMP/uv-install.sh"
        elif command -v wget >/dev/null 2>&1; then
            wget -O "$INSTALL_TEMP/uv-install.sh" https://astral.sh/uv/install.sh
        else
            echo "Erro: instale curl ou wget para baixar o uv." >&2
            exit 1
        fi
        UV_NO_MODIFY_PATH=1 UV_INSTALL_DIR="$HOME/.local/bin" sh "$INSTALL_TEMP/uv-install.sh"
        export PATH="$HOME/.local/bin:$PATH"
    fi
fi

if [[ "$INSTALL_MODE" != "wheel" ]]; then
    if [[ "$INSTALL_MODE" == "bundled" ]]; then
        echo "→ Preparando ADB e scrcpy oficiais com verificação SHA-256..."
        if [[ -n "$PREVIEW_ARCHIVE" ]]; then
            uv run --no-project --python 3.13 python "$SCRIPT_DIR/prepare-preview-tools.py" "$PREVIEW_ARCHIVE"
        else
            uv run --no-project --python 3.13 python "$SCRIPT_DIR/prepare-preview-tools.py" --download
        fi
        PY_ATV_REMOTE_NO_BUNDLED=0 uv build --python 3.13 --wheel --out-dir "$INSTALL_TEMP/wheels" "$PROJECT_ROOT"
    else
        PY_ATV_REMOTE_NO_BUNDLED=1 uv build --python 3.13 --wheel \
            --out-dir "$INSTALL_TEMP/wheels" "$PROJECT_ROOT"
    fi
    shopt -s nullglob
    INSTALL_WHEELS=("$INSTALL_TEMP"/wheels/*.whl)
    if [[ ${#INSTALL_WHEELS[@]} -ne 1 ]]; then
        echo "Erro: o build não produziu exatamente um wheel." >&2
        exit 1
    fi
    INSTALL_WHEEL="${INSTALL_WHEELS[0]}"
fi

echo "→ Instalando aplicativo e dependências Python..."
uv tool install --python 3.13 --force "$INSTALL_WHEEL"

APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
mkdir -p "$APPS_DIR" "$ICONS_DIR"
cp "$PROJECT_ROOT/packaging/py-atv-remote.svg" "$ICONS_DIR/py-atv-remote.svg"
cp "$PROJECT_ROOT/packaging/py-atv-remote.desktop" "$APPS_DIR/py-atv-remote.desktop"

# An absolute Exec works even when the desktop session has not loaded ~/.local/bin.
TOOL_BIN_DIR="$(uv tool dir --bin)"
uv run --no-project --python 3.13 python - "$APPS_DIR/py-atv-remote.desktop" "$TOOL_BIN_DIR/py-atv-remote" <<'PY'
import sys
from pathlib import Path
path = Path(sys.argv[1])
executable = sys.argv[2]
for char in ('\\', '"', '`', '$'):
    executable = executable.replace(char, '\\' + char)
# Desktop Entry escapes are decoded before the Exec quoting layer.
executable = executable.replace('\\', '\\\\').replace('%', '%%')
text = path.read_text()
path.write_text(text.replace('Exec=py-atv-remote\n', f'Exec="{executable}"\n'))
PY
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS_DIR" 2>/dev/null || true
fi

echo "✔ Instalação concluída. Abra py-atv-remote pelo menu do sistema."
echo "Terminal: $TOOL_BIN_DIR/py-atv-remote"
echo "Se uma versão anterior estiver aberta, feche-a antes de iniciar a nova."
