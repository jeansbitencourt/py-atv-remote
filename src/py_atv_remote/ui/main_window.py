"""Main desktop application window for py-atv-remote."""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from py_atv_remote.domain.keys import RemoteKey
from py_atv_remote.domain.models import ConnectionState, TvProfile, VolumeState
from py_atv_remote.infrastructure.config_store import ConfigStore
from py_atv_remote.services.async_runner import AsyncRunner
from py_atv_remote.services.events import EventBus
from py_atv_remote.services.remote_session import RemoteSessionService
from py_atv_remote.ui.keybindings import register_keybindings
from py_atv_remote.ui.widgets.dpad import DPad
from py_atv_remote.ui.widgets.repeat_button import RepeatButton
from py_atv_remote.ui.widgets.status_bar import StatusBar

LOGGER = logging.getLogger(__name__)


class MainWindow:
    """Main window controller for the remote control application."""

    def __init__(
        self,
        root: tk.Tk,
        config_store: ConfigStore,
        remote_session: RemoteSessionService,
        event_bus: EventBus,
        async_runner: AsyncRunner,
        open_device_manager: Callable[[], None],
        open_shortcuts_dialog: Callable[[], None],
    ) -> None:
        self._root = root
        self._config_store = config_store
        self._session = remote_session
        self._event_bus = event_bus
        self._runner = async_runner
        self._open_device_manager = open_device_manager
        self._open_shortcuts_dialog = open_shortcuts_dialog

        self._tvs: list[TvProfile] = []
        self._selected_tv_id: str | None = None

        self._setup_window()
        self._build_ui()
        self._setup_event_subscriptions()
        self._load_saved_tvs()

    def _setup_window(self) -> None:
        self._root.title("py-atv-remote")
        self._root.resizable(False, False)
        # Apply always-on-top preference
        always_on_top = self._config_store.get_always_on_top()
        self._root.attributes("-topmost", always_on_top)

    def _build_ui(self) -> None:
        # 1. Header Frame: TV Selector + Manage Devices (+) + Settings Menu (⚙)
        header_frame = ttk.Frame(self._root)
        header_frame.pack(fill=tk.X, padx=10, pady=4)

        self._tv_combobox_var = tk.StringVar()
        self._tv_combobox = ttk.Combobox(
            header_frame,
            textvariable=self._tv_combobox_var,
            state="readonly",
            width=22,
        )
        self._tv_combobox.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self._tv_combobox.bind("<<ComboboxSelected>>", self._on_tv_combobox_selected)

        self._btn_add_tv = ttk.Button(
            header_frame,
            text="+",
            width=3,
            command=self._open_device_manager,
        )
        self._btn_add_tv.pack(side=tk.LEFT, padx=(0, 4))

        self._btn_menu = ttk.Menubutton(header_frame, text="Opções", width=7)
        self._menu = tk.Menu(self._btn_menu, tearoff=0)
        self._menu_always_top_var = tk.BooleanVar(value=self._config_store.get_always_on_top())
        self._menu.add_checkbutton(
            label="Sempre no topo",
            variable=self._menu_always_top_var,
            command=self._toggle_always_on_top,
        )
        self._menu.add_command(label="Gerenciar TVs…", command=self._open_device_manager)
        self._menu.add_command(
            label="Editar Atalhos de Apps…",
            command=self._open_shortcuts_dialog,
        )
        self._btn_menu["menu"] = self._menu
        self._btn_menu.pack(side=tk.LEFT)

        # 2. Status Bar
        self._status_bar = StatusBar(self._root)
        self._status_bar.pack(fill=tk.X, padx=10, pady=4)

        # 3. Needs Pairing Banner (hidden by default)
        self._pairing_banner = ttk.Frame(self._root)
        self._lbl_pairing = ttk.Label(
            self._pairing_banner,
            text="Esta TV precisa ser pareada.",
            foreground="#2980b9",
        )
        self._lbl_pairing.pack(side=tk.LEFT, padx=4)
        self._btn_pair_banner = ttk.Button(
            self._pairing_banner,
            text="Parear Agora",
            command=self._open_device_manager,
        )
        self._btn_pair_banner.pack(side=tk.RIGHT, padx=4)

        # 4. Top Action Row: Power, Menu, Settings
        top_row = ttk.Frame(self._root)
        top_row.pack(fill=tk.X, padx=10, pady=4)

        self._btn_power = ttk.Button(
            top_row,
            text="Power",
            style="Power.TButton",
            command=self._on_power_pressed,
        )
        self._btn_power.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        self._btn_tv_menu = ttk.Button(
            top_row,
            text="Menu",
            command=lambda: self._send_key(RemoteKey.MENU),
        )
        self._btn_tv_menu.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        self._btn_tv_settings = ttk.Button(
            top_row,
            text="Ajustes",
            command=lambda: self._send_key(RemoteKey.SETTINGS),
        )
        self._btn_tv_settings.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 5. D-Pad Frame
        dpad_frame = ttk.Frame(self._root)
        dpad_frame.pack(padx=20, pady=8)
        self._dpad = DPad(dpad_frame, on_key=self._send_key)
        self._dpad.pack()

        # 6. System Row: Voltar, Início
        sys_row = ttk.Frame(self._root)
        sys_row.pack(fill=tk.X, padx=10, pady=4)

        self._btn_back = ttk.Button(
            sys_row,
            text="Voltar",
            command=lambda: self._send_key(RemoteKey.BACK),
        )
        self._btn_back.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        self._btn_home = ttk.Button(
            sys_row,
            text="Início",
            command=lambda: self._send_key(RemoteKey.HOME),
        )
        self._btn_home.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 7. Media Row: ◄◄, ►||, ►►
        media_row = ttk.Frame(self._root)
        media_row.pack(fill=tk.X, padx=10, pady=4)

        self._btn_rewind = ttk.Button(
            media_row,
            text="◄◄",
            width=6,
            style="Media.TButton",
            command=lambda: self._send_key(RemoteKey.MEDIA_REWIND),
        )
        self._btn_rewind.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        self._btn_play_pause = ttk.Button(
            media_row,
            text="►||",
            width=6,
            style="Media.TButton",
            command=lambda: self._send_key(RemoteKey.MEDIA_PLAY_PAUSE),
        )
        self._btn_play_pause.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        self._btn_fast_forward = ttk.Button(
            media_row,
            text="►►",
            width=6,
            style="Media.TButton",
            command=lambda: self._send_key(RemoteKey.MEDIA_FAST_FORWARD),
        )
        self._btn_fast_forward.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 8. Volume Row: Vol -, Mudo, Vol +
        vol_row = ttk.Frame(self._root)
        vol_row.pack(fill=tk.X, padx=10, pady=4)

        self._btn_vol_down = RepeatButton(
            vol_row,
            text="Vol -",
            command=lambda: self._send_key(RemoteKey.VOLUME_DOWN),
        )
        self._btn_vol_down.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        self._btn_mute = ttk.Button(
            vol_row,
            text="Mudo",
            width=6,
            command=lambda: self._send_key(RemoteKey.MUTE),
        )
        self._btn_mute.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        self._btn_vol_up = RepeatButton(
            vol_row,
            text="Vol +",
            command=lambda: self._send_key(RemoteKey.VOLUME_UP),
        )
        self._btn_vol_up.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 9. App Shortcuts Container
        self._shortcuts_frame = ttk.Frame(self._root)
        self._shortcuts_frame.pack(fill=tk.X, padx=10, pady=4)
        self.refresh_app_shortcuts()

        # 10. Text Input Row
        text_row = ttk.Frame(self._root)
        text_row.pack(fill=tk.X, padx=10, pady=(4, 10))

        self._text_var = tk.StringVar()
        self._txt_input = ttk.Entry(text_row, textvariable=self._text_var)
        self._txt_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self._txt_input.bind("<Return>", lambda _e: self._on_send_text())

        self._btn_send_text = ttk.Button(
            text_row,
            text="Enviar",
            command=self._on_send_text,
        )
        self._btn_send_text.pack(side=tk.RIGHT)

        def is_ctrl_enabled() -> bool:
            return self._session.state in (
                ConnectionState.CONNECTED,
                ConnectionState.RECONNECTING,
            )

        # Register physical keyboard shortcuts
        register_keybindings(
            self._root,
            on_key=self._send_key,
            is_enabled=is_ctrl_enabled,
        )

        self._update_controls_state(ConnectionState.IDLE)

    def _setup_event_subscriptions(self) -> None:
        self._event_bus.on_state(self._on_state_event)
        self._event_bus.on_volume(self._on_volume_event)
        self._event_bus.on_current_app(self._on_current_app_event)
        self._event_bus.on_error(self._on_error_event)

    def _load_saved_tvs(self) -> None:
        self._tvs = self._config_store.list_tvs()
        names = [tv.name for tv in self._tvs]
        self._tv_combobox["values"] = names

        last_id = self._config_store.get_last_selected_id()
        selected_index = -1
        if last_id:
            for idx, tv in enumerate(self._tvs):
                if tv.id == last_id:
                    selected_index = idx
                    break

        if selected_index >= 0:
            self._tv_combobox.current(selected_index)
            self._selected_tv_id = self._tvs[selected_index].id
            self._connect_to_selected_tv()
        elif self._tvs:
            self._tv_combobox.current(0)
            self._selected_tv_id = self._tvs[0].id
            self._connect_to_selected_tv()
        else:
            self._tv_combobox_var.set("Nenhuma TV cadastrada")

    def refresh_tvs(self, selected_tv_id: str | None = None) -> None:
        """Reload the list of saved TVs in the selector dropdown."""
        self._tvs = self._config_store.list_tvs()
        names = [tv.name for tv in self._tvs]
        self._tv_combobox["values"] = names

        last_id = self._config_store.get_last_selected_id()
        target_id = selected_tv_id or self._selected_tv_id or last_id
        selected_idx = -1
        if target_id:
            for idx, tv in enumerate(self._tvs):
                if tv.id == target_id:
                    selected_idx = idx
                    break

        if selected_idx >= 0:
            self._tv_combobox.current(selected_idx)
            self._selected_tv_id = self._tvs[selected_idx].id
        elif self._tvs:
            self._tv_combobox.current(0)
            self._selected_tv_id = self._tvs[0].id
        else:
            self._tv_combobox_var.set("Nenhuma TV cadastrada")
            self._selected_tv_id = None

    def refresh_app_shortcuts(self) -> None:
        """Rebuild app shortcut buttons from config."""
        for child in self._shortcuts_frame.winfo_children():
            child.destroy()

        shortcuts = self._config_store.get_app_shortcuts()
        if not shortcuts:
            return

        # Display up to 5 shortcuts in a clean row
        for item in shortcuts[:5]:
            link_target = item.link
            btn = ttk.Button(
                self._shortcuts_frame,
                text=item.label,
                command=self._make_launch_handler(link_target),
            )
            btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

    def _make_launch_handler(self, link: str) -> Callable[[], None]:
        return lambda: self._session.launch_app(link)

    def _on_tv_combobox_selected(self, _event: tk.Event[tk.Misc]) -> None:
        idx = self._tv_combobox.current()
        if 0 <= idx < len(self._tvs):
            tv = self._tvs[idx]
            self._selected_tv_id = tv.id
            self._connect_to_selected_tv()

    def _connect_to_selected_tv(self) -> None:
        if not self._selected_tv_id:
            return
        tv_id = self._selected_tv_id
        self._runner.submit(self._session.select_tv(tv_id))

    def _send_key(self, key: RemoteKey) -> None:
        self._session.send_key(key)

    def _on_send_text(self) -> None:
        text = self._text_var.get()
        if text:
            self._session.send_text(text)
            self._text_var.set("")

    def _on_power_pressed(self) -> None:
        self._runner.submit(self._session.power())

    def _toggle_always_on_top(self) -> None:
        val = self._menu_always_top_var.get()
        self._root.attributes("-topmost", val)
        self._config_store.set_always_on_top(val)

    def _on_state_event(self, state: ConnectionState, profile: TvProfile | None) -> None:
        self._status_bar.update_state(state)
        self._update_controls_state(state)

        if state == ConnectionState.NEEDS_PAIRING:
            self._pairing_banner.pack(fill=tk.X, padx=10, pady=2, before=self._status_bar)
        else:
            self._pairing_banner.pack_forget()

    def _on_volume_event(self, volume: VolumeState) -> None:
        self._status_bar.update_volume(volume)

    def _on_current_app_event(self, app_id: str) -> None:
        self._status_bar.update_current_app(app_id)

    def _on_error_event(self, message: str, _exc: Exception | None = None) -> None:
        # Display modal alert on explicit failures
        messagebox.showerror("Erro de Comunicação", message, parent=self._root)

    def _update_controls_state(self, state: ConnectionState) -> None:
        """Enable or disable remote control widgets based on connection state."""
        connected = state in (ConnectionState.CONNECTED, ConnectionState.RECONNECTING)
        btn_state = tk.NORMAL if connected else tk.DISABLED

        self._dpad.set_enabled(connected)
        for btn in (
            self._btn_tv_menu,
            self._btn_tv_settings,
            self._btn_back,
            self._btn_home,
            self._btn_rewind,
            self._btn_play_pause,
            self._btn_fast_forward,
            self._btn_vol_down,
            self._btn_mute,
            self._btn_vol_up,
            self._btn_send_text,
        ):
            btn["state"] = btn_state

        for child in self._shortcuts_frame.winfo_children():
            if isinstance(child, ttk.Button):
                child["state"] = btn_state

        # Power button remains clickable anytime so user can trigger WoL or reconnect
        self._btn_power["state"] = tk.NORMAL
