# AGENTS.md - Developer and Agent Guide for py-atv-remote

This document serves as the architectural reference and development playbook for agents and engineers working on the **py-atv-remote** codebase.

---

## 1. Project Overview

`py-atv-remote` is a native desktop remote control application for Android TV and Google TV built with Python, PyQt6, and the Google Remote V2 protocol (mTLS on ports 6466/6467). It supports multiple TVs on the local network, persistent TLS sessions, automatic DHCP IP synchronization, Wake-on-LAN, and desktop environment integration.

---

## 2. Layered Architecture & Dependency Rule

The project strictly follows layered clean architecture. Dependencies only point inward:

```
UI (PyQt6 / Qt)
    ↓
Services (Orchestration & Application Logic)
    ↓
Infrastructure (Adapters, Persistence, Network IO)
    ↓
Domain (Entities, Value Objects, Enums, Errors)
```

- **Domain (`src/py_atv_remote/domain/`)**: Pure Python code with zero external I/O or GUI dependencies.
  - `models.py`: `TvProfile`, `DiscoveredTv`, `ConnectionState`, `VolumeState`, `AppShortcut`.
  - `keys.py`: `RemoteKey` enum mapped to Google Remote V2 keycode constants.
  - `errors.py`: Hierarchical domain exceptions (`DomainError`, `TvUnreachableError`, `PairingRequiredError`, `InvalidPinError`, etc.).

- **Infrastructure (`src/py_atv_remote/infrastructure/`)**:
  - `paths.py`: XDG directory resolution (`~/.config/py-atv-remote/`, permissions `0700`).
  - `config_store.py`: Atomic JSON persistence (`NamedTemporaryFile` + `fsync` + `replace`) with schema versioning and corrupted file recovery.
  - `cert_store.py`: Per-TV certificate and key lifecycle management (`chmod 0600`).
  - `mdns_browser.py`: `AsyncZeroconf` service browser for `_androidtvremote2._tcp.local.`.
  - `subnet_scanner.py`: Asynchronous TCP port 6466 probe fallback for networks blocking mDNS.
  - `atv_client.py`: Adapter wrapping `androidtvremote2.AndroidTVRemote`, translating third-party exceptions to domain errors.
  - `arp.py`: Hardware MAC resolution via `/proc/net/arp`.
  - `wol.py`: Wake-on-LAN 102-byte magic packet generation and UDP broadcast.

- **Services (`src/py_atv_remote/services/`)**:
  - `async_runner.py`: Owns an asyncio event loop running in a dedicated background daemon thread.
  - `events.py`: Typed event bus and `Dispatcher` protocol.
  - `remote_session.py`: Coordinates the single active TV persistent TLS session, volume callbacks, app state, and command dispatching.
  - `discovery_service.py`: Coordinates mDNS discovery and subnet scanning, and synchronizes dynamic DHCP IP updates with `ConfigStore`.
  - `pairing_service.py`: Coordinates mTLS cert generation, PIN validation handshake, and profile creation.

- **UI (`src/py_atv_remote/ui/`)**:
  - `qt_dispatcher.py`: Bridges the background asyncio loop and Qt GUI thread using thread-safe Qt Signals/Slots (`pyqtSignal(object)`).
  - `main_window.py`: Primary remote control window with TV selector, D-Pad, media keys, volume, text input, and status bar.
  - `device_manager.py`: Dialog for live network discovery, pairing, manual IP probing, and profile management.
  - `pair_dialog.py`: PIN entry modal.
  - `shortcuts_dialog.py`: Customization dialog for app launcher shortcuts.
  - `keybindings.py`: Physical keyboard shortcut mapping and focus management.
  - `widgets/`: Reusable components (`RepeatButton`, `DPad`, `StatusBar`).

---

## 3. Strict Concurrency & Threading Invariants

1. **Qt Main Thread Invariant**: All Qt widget creation, geometry management, and UI state mutations **MUST** execute exclusively on the main thread.
2. **Never Call Qt Directly From Background Threads**: Never invoke widget methods directly from asyncio tasks or background threads. Always post through `Dispatcher.post()` or `QtDispatcher.post()`, or emit typed events via `EventBus`.
3. **Non-Blocking Main Loop**: Network I/O, TLS handshakes, mDNS browsing, and port probes **MUST NEVER** execute on the main thread. Always schedule them onto `AsyncRunner` using `runner.submit(coroutine)`.
4. **Orderly Shutdown**: When the application closes (`closeEvent` / `aboutToQuit`), the session must disconnect, discovery browser must be cancelled, background runner tasks must be cancelled, and loops properly closed.

---

## 4. Coding Conventions & Standards

- **Typing**: Strict type annotations (`mypy --strict`). Do not use untyped `Any` unless interfacing with dynamic third-party libraries.
- **Error Handling**: Catch external library exceptions (e.g. `androidtvremote2.CannotConnect`, `OSError`) at the infrastructure layer and translate them into domain exceptions before bubbling up to services or UI.
- **No TODOs**: Write complete, self-contained, production-ready code.
- **Language Policy**:
  - UI strings, user-facing dialogs, and `README.md` are in **Portuguese (PT-BR)**.
  - Code, variable names, docstrings, tests, and `AGENTS.md` are in **English**.
  - Git commits follow **Conventional Commits** in **English** (e.g. `feat(discovery): ...`, `fix(ui): ...`).

---

## 5. Development, Verification & CI Commands

All commands are executed using `uv`:

```bash
# Run automated test suite
uv run pytest -q

# Static type check with mypy (strict mode)
uv run mypy src

# Linting with Ruff
uv run ruff check .

# Code formatting verification with Ruff
uv run ruff format --check .

# Auto-format and auto-fix linter issues
uv run ruff check --fix --unsafe-fixes .
uv run ruff format .
```

---

## 6. Extending the Codebase

### Adding a New Remote Key
1. Add the enum member to `RemoteKey` in `src/py_atv_remote/domain/keys.py` (matching the `KEYCODE_*` string in `androidtvremote2`).
2. If repeatable when held down, include it in `RemoteKey.is_repeatable`.
3. In `src/py_atv_remote/ui/keybindings.py`, map the physical keyboard symbol to the new `RemoteKey`.
4. Add a button widget in `MainWindow._build_ui()` using `RepeatButton` (if repeatable) or `ttk.Button`.

### Adding a New Default App Shortcut
1. Add an `AppShortcut` instance to `DEFAULT_APP_SHORTCUTS` in `src/py_atv_remote/infrastructure/config_store.py`.
2. Format a human-readable display label in `StatusBar._format_app_name()` in `src/py_atv_remote/ui/widgets/status_bar.py`.
