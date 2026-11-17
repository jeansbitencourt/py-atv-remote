# Distribuição da visualização

O manifesto fixa o release oficial scrcpy 5.0.1 para Linux x86_64, incluindo
ADB 37.0.1, servidor scrcpy e cliente. O SHA-256 foi conferido contra a documentação
oficial e contra o arquivo baixado. Não há download durante a execução do app.

Após clonar o repositório, a instalação completa é automática:

```bash
./scripts/install-desktop.sh
```

O script prepara uv/Python quando necessário, baixa o release fixado, verifica o
SHA-256, gera o wheel em diretório temporário e instala no ambiente de usuário.
O download fica em `build/preview-tools` para reutilização. O arquivo é verificado
novamente antes de cada preparação. Nenhum binário é baixado durante o uso do app.

Use `--without-preview` para um pacote sem ferramentas nativas, mesmo que elas
já tenham sido preparadas no repositório. Esse modo continua permitindo ferramentas
instaladas pelo usuário no PATH. Use `--archive ARQUIVO` para fornecer o tar.gz oficial.

Para preparar manualmente um pacote local de validação:

```bash
curl -fL https://github.com/Genymobile/scrcpy/releases/download/v5.0.1/scrcpy-linux-x86_64-v5.0.1.tar.gz -o /tmp/scrcpy-release.tar.gz
uv run python scripts/prepare-preview-tools.py /tmp/scrcpy-release.tar.gz
uv build --wheel
```

O wheel recebe a tag `py3-none-linux_x86_64`; sem ferramentas preparadas, o build
continua sendo Python puro e usa executáveis instalados no sistema. O instalador
desktop aceita o caminho do wheel como primeiro argumento.

## Limite para publicação

Este pacote é para validação local. O arquivo oficial contém a licença Apache-2.0
do scrcpy, mas não fornece um inventário completo dos avisos de todas as bibliotecas
estaticamente ligadas. Antes de publicar ou redistribuir o wheel, completar o
inventário e as obrigações de distribuição de ADB, FFmpeg, SDL, dav1d e libusb,
incluindo fontes correspondentes e possibilidade de relink quando exigido.
Não presumir que a licença do scrcpy cobre essas dependências ou todo o SDK Android.

Referências de origem:

- https://github.com/Genymobile/scrcpy/blob/v5.0.1/release/build_linux.sh
- https://github.com/Genymobile/scrcpy/tree/v5.0.1/app/deps
- https://github.com/Genymobile/scrcpy/blob/v5.0.1/LICENSE

O pacote ainda precisa de teste em distribuição limpa, X11 e Wayland. Bibliotecas
básicas do sistema e drivers gráficos não são substituídos pelo wheel.
