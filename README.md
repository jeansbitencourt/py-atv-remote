# py-atv-remote

Controle remoto desktop nativo para **Android TV** e **Google TV**, desenvolvido em Python e PyQt6 utilizando o protocolo oficial **Google Remote V2 (mTLS)** sobre as portas `6466` e `6467`. Possui interface moderna com tema escuro elegante, renderização vetorial nítida com anti-aliasing nativo e suporte completo a múltiplos dispositivos.

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
- **Atalhos do Teclado Físico**: Controle a TV com setas, teclas de mídia, volume e atalhos de sistema. Consulte a lista completa no menu de opções do aplicativo.
- **Envio de Texto Direto**: Digite buscas, URLs e senhas no computador e envie diretamente para o campo de texto ativo na TV.
- **Atalhos Customizáveis para Apps**: Abra YouTube, Netflix, Prime Video, Disney+, Globoplay ou adicione seus próprios aplicativos.
- **Janela Sempre no Topo (Always on Top)**: Fixe o controle sobre outras janelas enquanto assiste ou trabalha.
- **Integração com Desktop Linux**: Inclui atalho `.desktop` e ícone vetorial SVG para o lançador de aplicativos do KDE Plasma e GNOME.

---

## 📋 Requisitos

- Sistema operacional Linux (testado em Fedora, Bazzite, Kinoite, Ubuntu, Arch).
- **uv** (recomendado para execução rápida com ambiente virtual isolado) ou Python 3.10+.
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

Após clonar o projeto, execute o instalador **sem sudo** em Linux x86_64:

O script instala o `uv` se necessário, obtém Python 3.13, baixa e verifica ADB/scrcpy
oficiais, gera o pacote e instala o aplicativo com suas dependências Python e atalho.
Você não precisa gerar nem baixar um wheel manualmente. É necessário acesso à
internet na primeira instalação e `curl` ou `wget` se o `uv` ainda não estiver instalado.
O wheel é apenas o formato de pacote usado internamente nessa instalação.

Para integrar o aplicativo ao menu do sistema (KDE Plasma, GNOME, etc.):

```bash
./scripts/install-desktop.sh
```

Após a execução, o **py-atv-remote** estará disponível no lançador de aplicativos com ícone próprio e poderá ser aberto pelo terminal como `py-atv-remote`.

Para instalar o controle sem incluir ADB/scrcpy:

```bash
./scripts/install-desktop.sh --without-preview
```

Também é possível fornecer um release oficial já baixado (`--archive arquivo.tar.gz`)
ou um pacote `.whl` existente como argumento. Releases fornecidos são verificados
pelo SHA-256 fixado no projeto. Execute o script novamente para atualizar a instalação.

As ferramentas incluídas suportam **Linux x86_64 com glibc e desktop gráfico**.
Não há garantia de funcionamento em toda distribuição Linux; ARM, Alpine/musl e
bibliotecas gráficas incompatíveis exigem suporte específico. O script não instala
drivers nem pacotes do sistema com privilégios administrativos.

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
| `I` | Alternar Entradas (`TV_INPUT`) |
| `P` | Ligar / desligar (ou tentar Wake-on-LAN quando offline) |
| `Espaço` | Reproduzir / Pausar (`MEDIA_PLAY_PAUSE`) |
| `J` / `L` | Rebobinar / avançar |
| `+` / `KP_Add` / `=` | Aumentar Volume (`VOLUME_UP`) |
| `-` / `KP_Subtract` | Diminuir Volume (`VOLUME_DOWN`) |
| `M` | Alternar Mudo (`MUTE`) |

Os atalhos funcionam quando a janela principal está ativa, mesmo que um botão esteja com foco. No campo de texto, as teclas continuam editando o texto; `Enter` envia o texto e `Escape` tira o foco do campo. Menus, seletores abertos e diálogos mantêm o comportamento normal.

Também é possível consultar essa lista no menu de opções, em **Consultar Atalhos do Teclado…**.

---

## Visualização opcional da TV

No menu **⚙ → Visualização da TV → Configurar e ativar…**, ative o recurso para a
TV selecionada. O controle remoto normal continua funcionando sem ADB.

1. Na TV, habilite Opções do desenvolvedor (em Sobre, pressione várias vezes o
   número da compilação). Abra **Depuração sem fio → Parear com código**.
2. No app, informe o endereço/porta de pareamento e o código de seis dígitos.
3. Clique em **Parear com código**. O app tenta descobrir a porta de conexão por
   mDNS; se não encontrar, informe a porta da tela principal de Depuração sem fio.
   **A porta de conexão é diferente da porta de pareamento.**
4. Clique em **Conectar e confirmar TV…**, confira modelo/endereço e salve com a
   ativação marcada.
5. No menu, escolha **Abrir visualização**. A janela externa do scrcpy exibe a TV
   sem áudio nem comandos. Use a janela principal para controlar a TV.

Para TV já pareada, basta descobrir/informar a porta de conexão e confirmar a TV.
Em aparelhos antigos, escolha **ADB TCP/IP tradicional** e informe a porta de
rede habilitada pelo aparelho (5555 é apenas uma sugestão). Autorize o computador
na TV, se solicitado. Depuração USB sozinha pode não habilitar acesso pela rede.
Os nomes dos menus variam por fabricante.

O menu inclui ajuda e verificação das ferramentas. O recurso fica desativado por
padrão e é configurado individualmente por TV. Para desativar, desmarque a ativação
e salve. **Esquecer configuração local** não revoga a autorização na TV; faça isso
em Depuração sem fio → Dispositivos pareados → Esquecer.

Uma única janela de visualização fica ativa. Trocar a TV ou sair do app encerra a
visualização anterior. Fechar somente a janela scrcpy mantém o controle funcionando.
Se o aparelho não informar identificador estável, será preciso confirmar a TV a
cada abertura. O app não grava vídeo, screenshots, chaves ADB ou códigos de pareamento;
as credenciais do computador são gerenciadas pelo próprio ADB.

Use uma rede confiável. Redes guest/VLAN e isolamento Wi-Fi podem impedir conexão
ou mDNS. Conteúdo protegido pode aparecer preto; problemas de encoder ou rede
também podem causar falha. O recurso não contorna DRM. IPv6 não é suportado nesta versão.

### Ferramentas e pacote local

Linux x86_64: o pacote de validação pode incluir ADB e scrcpy, sem instalação global.
Veja [como gerar o pacote](packaging/PREVIEW_DISTRIBUTION.md). Executando pelo código,
também é possível usar `adb` e `scrcpy` no PATH ou os caminhos absolutos definidos em
`PY_ATV_REMOTE_ADB` e `PY_ATV_REMOTE_SCRCPY` (sobrepõem a seleção automática).
Não há downloads ao abrir a visualização. O app não encerra o servidor ADB compartilhado.

**Validação em TV real, distribuição limpa e ambientes gráficos ainda pendente.**

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
