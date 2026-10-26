# py-atv-remote

Controle remoto desktop nativo para **Android TV** e **Google TV**, desenvolvido em Python e Tkinter utilizando o protocolo oficial **Google Remote V2 (mTLS)** sobre as portas `6466` e `6467`.

Diferente de soluções baseadas em ADB, o **py-atv-remote** conecta-se exatamente como o aplicativo móvel oficial do Google Home / Google TV: **sem necessidade de ativar o modo de desenvolvedor, sem emuladores e sem portas de depuração expostas na TV**.

Projetado especificamente para residências com **múltiplas televisões na mesma rede**, o aplicativo faz a varredura mDNS contínua, permitindo selecionar qual TV controlar ou parear novas telas com apenas alguns cliques.

---

## 🚀 Funcionalidades

- **Múltiplas TVs na Mesma Rede**: Lista todas as Android/Google TVs disponíveis no seletor da barra superior. Alterne entre TVs (ex.: Sala, Quarto) instantaneamente.
- **Pareamento Seguro por TV**: Cada televisão possui seu próprio par de chaves e certificados mTLS (`cert_{id}.pem` e `key_{id}.pem`) salvos de forma isolada e com permissões estritas (`0600`).
- **Sessão TLS Persistente**: Mantém o canal TLS aberto enquanto a TV estiver selecionada, eliminando a latência de handshake (200–500ms) a cada tecla pressionada.
- **Detecção e Atualização Automática de IP (DHCP)**: O app rastreia o identificador único de hardware da TV via mDNS. Se o roteador alterar o endereço IP da TV, o perfil é atualizado automaticamente sem necessidade de novo pareamento.
- **Fallback de Varredura TCP e IP Manual**: Caso o roteador bloqueie tráfego multicast/mDNS, a ferramenta oferece varredura direta de sub-rede na porta 6466 e inserção manual de IP.
- **Wake-on-LAN (WoL)**: Aprende dinamicamente o MAC de rede da TV via tabela ARP do Linux e envia magic packets para ligar TVs em standby profundo.
- **Repetição ao Segurar**: Pressione e segure setas do D-Pad ou botões de Volume para repetição rápida e suave.
- **Atalhos do Teclado Físico**: Navegue com as setas, dê `Enter` para OK, `Esc` para voltar, `Espaço` para Play/Pause, `+`/`-` para volume e `M` para mudo.
- **Envio de Texto Direto**: Digite buscas, URLs e senhas no computador e envie diretamente para o campo de texto ativo na TV.
- **Atalhos Customizáveis para Apps**: Abra YouTube, Netflix, Prime Video, Disney+, Globoplay ou adicione seus próprios aplicativos.
- **Janela Sempre no Topo (Always on Top)**: Fixe o controle sobre outras janelas enquanto assiste ou trabalha.
- **Integração com Desktop Linux**: Inclui atalho `.desktop` e ícone vetorial SVG para o lançador de aplicativos do KDE Plasma e GNOME.

---

## 📋 Requisitos

- Sistema operacional Linux (testado em Fedora, Bazzite, Kinoite, Ubuntu, Arch).
- **uv** (recomendado para empacotamento rápido com Python 3.13 e Tkinter nativo) ou Python 3.12+ com suporte a Tkinter.
- TV e computador conectados na mesma rede local/Wi-Fi (portas `6466` e `6467` liberadas).

---

## 📥 Instalação e Execução

### Opção 1: Executar diretamente com `uv` (Recomendado)

O [uv](https://github.com/astral-sh/uv) gerencia a versão correta do Python e as dependências isoladamente:

```bash
# Se ainda não tiver o uv instalado:
curl -LsSf https://astral.sh/uv/install.sh | sh

# No diretório do projeto, execute:
uv run py-atv-remote
```

Você também pode executar diretamente pelo script de entrada:
```bash
uv run python main.py
```

### Opção 2: Instalar no menu de aplicativos do Linux (.desktop)

Para integrar o aplicativo ao menu do sistema (KDE Plasma, GNOME, etc.):

```bash
./scripts/install-desktop.sh
```

Após a execução, o **py-atv-remote** estará disponível no lançador de aplicativos com ícone próprio e poderá ser aberto pelo terminal como `py-atv-remote`.

Para desinstalar os atalhos do sistema:
```bash
./scripts/uninstall-desktop.sh
```

### Opção 3: Usando `pip` e ambiente virtual padrão

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

---

## 📺 Como Parear uma TV pela Primeira Vez

1. Ligue a sua TV Android ou Google TV e certifique-se de que o computador e a TV estejam conectados na mesma rede Wi-Fi.
2. Abra o **py-atv-remote**.
3. Clique no botão **＋** no canto superior direito para abrir o **Gerenciador de TVs**.
4. As televisões encontradas na rede aparecerão automaticamente na lista:
   - Selecione a TV desejada e clique em **Parear TV…** (ou dê duplo clique).
5. Um código PIN de 6 dígitos será exibido na tela da televisão.
6. Digite o código no aplicativo e clique em **Confirmar PIN**.
7. Pronto! A TV está pareada e pronta para ser controlada. O pareamento fica salvo e não precisa ser repetido nas próximas vezes.

> **Dica:** Se a TV não aparecer automaticamente na lista devido a configurações restritas do roteador (bloqueio de multicast/mDNS), clique em **Adicionar por IP…** e digite o endereço IPv4 da TV (exemplo: `192.168.2.104`).

---

## ⌨️ Atalhos do Teclado Físico

| Tecla | Ação |
|---|---|
| `▲`, `▼`, `◀`, `▶` (Setas) | Navegação Direcional (D-Pad) |
| `Enter` / `KP_Enter` | Selecionar / OK |
| `Escape` / `Backspace` | Voltar (`BACK`) |
| `Home` / `H` | Tela Inicial (`HOME`) |
| `Espaço` | Reproduzir / Pausar (`MEDIA_PLAY_PAUSE`) |
| `+` / `KP_Add` / `=` | Aumentar Volume (`VOLUME_UP`) |
| `-` / `KP_Subtract` | Diminuir Volume (`VOLUME_DOWN`) |
| `M` | Alternar Mudo (`MUTE`) |

*(Os atalhos de navegação e mídia são pausados automaticamente quando você clica e digita no campo de envio de texto).*

---

## ⚙️ Configuração e Certificados

Seguindo as especificações do XDG Base Directory, todos os arquivos gerados pelo usuário ficam armazenados fora do repositório:

- **Configuração principal**: `~/.config/py-atv-remote/config.json`
- **Certificados e chaves mTLS**: `~/.config/py-atv-remote/certs/`
  - `cert_{id}.pem` (certificado público da sessão)
  - `key_{id}.pem` (chave privada RSA gerada localmente, protegida com permissão `0600`)

---

## 🔌 Wake-on-LAN e Dicas de Rede

- **Standby normal**: Em modo de espera normal, as TVs Android continuam com a interface de rede ativa. O botão **⏻ Power** liga e desliga a TV normalmente pela conexão TLS.
- **Standby profundo**: Para ligar televisões em modo de economia profunda via Wake-on-LAN (WoL), certifique-se de que a opção **"Ligar com Wi-Fi (WoWLAN)"** ou **"Ativação pela Rede"** esteja habilitada nas configurações de Rede da sua televisão (em TVs Philips: *Configurações > Rede e Internet > Ligar com Wi-Fi*).
- **Portas de Rede**: O protocolo Google Remote V2 requer que as portas TCP `6466` (comandos/estado) e `6467` (pareamento/certificados) estejam acessíveis entre o computador e as televisões.

---

## 🛠️ Desenvolvimento e Testes

O projeto utiliza **Ruff** para formatação e linting, **Mypy** em modo estrito para checagem estática de tipos e **Pytest** para a suíte de testes automatizados:

```bash
# Executar a suíte de testes
uv run pytest -q

# Verificar tipagem estática (modo estrito)
uv run mypy src

# Executar linter e checagem de estilo
uv run ruff check .
uv run ruff format --check .
```

---

## 📄 Licença

Distribuído sob licença MIT. Consulte o arquivo de licença ou metadados do pacote para mais detalhes.
