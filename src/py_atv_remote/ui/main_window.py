"""Main desktop application window for py-atv-remote built with CustomTkinter."""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox
from typing import Any

import customtkinter as ctk

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
        root: ctk.CTk,
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
        btn_common: dict[str, Any] = {
            "fg_color": ("#d4d4d8", "#3f3f46"),
            "hover_color": ("#a1a1aa", "#52525b"),
            "text_color": ("#18181b", "#f4f4f5"),
            "corner_radius": 8,
            "height": 34,
            "font": ("Liberation Sans", 11),
        }

        # 1. Header Frame: TV Selector + Manage Devices (+) + Settings Menu (⚙)
        header_frame = ctk.CTkFrame(self._root, fg_color="transparent")
        header_frame.pack(fill="x", padx=12, pady=(10, 6))

        self._tv_selector_var = tk.StringVar()
        self._tv_selector = ctk.CTkOptionMenu(
            header_frame,
            variable=self._tv_selector_var,
            values=["Nenhuma TV cadastrada"],
            command=self._on_tv_option_selected,
            height=32,
            corner_radius=8,
            fg_color=("#e4e4e7", "#27272a"),
            button_color=("#d4d4d8", "#3f3f46"),
            button_hover_color=("#a1a1aa", "#52525b"),
            text_color=("#18181b", "#f4f4f5"),
            dropdown_fg_color=("#f4f4f5", "#27272a"),
            dropdown_text_color=("#18181b", "#f4f4f5"),
            dropdown_hover_color=("#d4d4d8", "#3f3f46"),
            font=("Liberation Sans", 11),
        )
        self._tv_selector.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self._btn_add_tv = ctk.CTkButton(
            header_frame,
            text="+",
            width=34,
            height=32,
            corner_radius=8,
            font=("Liberation Sans", 14, "bold"),
            fg_color=("#d4d4d8", "#3f3f46"),
            hover_color=("#a1a1aa", "#52525b"),
            text_color=("#18181b", "#f4f4f5"),
            command=self._open_device_manager,
        )
        self._btn_add_tv.pack(side="left", padx=(0, 6))

        self._btn_menu = ctk.CTkButton(
            header_frame,
            text="⚙",
            width=34,
            height=32,
            corner_radius=8,
            font=("Liberation Sans", 13),
            fg_color=("#d4d4d8", "#3f3f46"),
            hover_color=("#a1a1aa", "#52525b"),
            text_color=("#18181b", "#f4f4f5"),
            command=self._show_options_menu,
        )
        self._btn_menu.pack(side="left")

        # Native popup menu for options
        self._menu = tk.Menu(self._root, tearoff=0)
        self._menu_always_top_var = tk.BooleanVar(value=self._config_store.get_always_on_top())
        self._menu.add_checkbutton(
            label="Sempre no topo",
            variable=self._menu_always_top_var,
            command=self._toggle_always_on_top,
        )
        self._menu.add_separator()
        self._menu.add_command(label="Gerenciar TVs…", command=self._open_device_manager)
        self._menu.add_command(
            label="Editar Atalhos de Apps…",
            command=self._open_shortcuts_dialog,
        )

        # 2. Status Bar
        self._status_bar = StatusBar(self._root)
        self._status_bar.pack(fill="x", padx=12, pady=(0, 6))

        # 3. Needs Pairing Banner (hidden by default)
        self._pairing_banner = ctk.CTkFrame(self._root, fg_color="#1e3a8a", corner_radius=8)
        self._lbl_pairing = ctk.CTkLabel(
            self._pairing_banner,
            text="Esta TV precisa ser pareada.",
            font=("Liberation Sans", 11),
            text_color="#ffffff",
        )
        self._lbl_pairing.pack(side="left", padx=8, pady=4)
        self._btn_pair_banner = ctk.CTkButton(
            self._pairing_banner,
            text="Parear Agora",
            width=80,
            height=26,
            corner_radius=6,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=("Liberation Sans", 10, "bold"),
            command=self._open_device_manager,
        )
        self._btn_pair_banner.pack(side="right", padx=8, pady=4)

        # 4. Top Action Row: Power, Menu, Settings
        top_row = ctk.CTkFrame(self._root, fg_color="transparent")
        top_row.pack(fill="x", padx=12, pady=4)

        self._btn_power = ctk.CTkButton(
            top_row,
            text="Power",
            font=("Liberation Sans", 11, "bold"),
            fg_color="#dc2626",
            hover_color="#b91c1c",
            text_color="#ffffff",
            corner_radius=8,
            height=34,
            command=self._on_power_pressed,
        )
        self._btn_power.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self._btn_tv_menu = ctk.CTkButton(
            top_row,
            text="Menu",
            command=lambda: self._send_key(RemoteKey.MENU),
            **btn_common,
        )
        self._btn_tv_menu.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self._btn_tv_settings = ctk.CTkButton(
            top_row,
            text="Ajustes",
            command=lambda: self._send_key(RemoteKey.SETTINGS),
            **btn_common,
        )
        self._btn_tv_settings.pack(side="left", fill="x", expand=True)

        # 5. D-Pad Frame
        dpad_frame = ctk.CTkFrame(self._root, fg_color="transparent")
        dpad_frame.pack(padx=16, pady=8)
        self._dpad = DPad(dpad_frame, on_key=self._send_key)
        self._dpad.pack()

        # 6. System Row: Voltar, Início
        sys_row = ctk.CTkFrame(self._root, fg_color="transparent")
        sys_row.pack(fill="x", padx=12, pady=4)

        self._btn_back = ctk.CTkButton(
            sys_row,
            text="Voltar",
            command=lambda: self._send_key(RemoteKey.BACK),
            **btn_common,
        )
        self._btn_back.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self._btn_home = ctk.CTkButton(
            sys_row,
            text="Início",
            command=lambda: self._send_key(RemoteKey.HOME),
            **btn_common,
        )
        self._btn_home.pack(side="left", fill="x", expand=True)

        # 7. Media Row: ◄◄, ►||, ►►
        media_common: dict[str, Any] = {
            "fg_color": ("#cbd5e1", "#334155"),
            "hover_color": ("#94a3b8", "#475569"),
            "text_color": ("#18181b", "#f4f4f5"),
            "corner_radius": 8,
            "height": 34,
            "font": ("Liberation Sans", 12, "bold"),
        }
        media_row = ctk.CTkFrame(self._root, fg_color="transparent")
        media_row.pack(fill="x", padx=12, pady=4)

        self._btn_rewind = ctk.CTkButton(
            media_row,
            text="◄◄",
            command=lambda: self._send_key(RemoteKey.MEDIA_REWIND),
            **media_common,
        )
        self._btn_rewind.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self._btn_play_pause = ctk.CTkButton(
            media_row,
            text="►||",
            command=lambda: self._send_key(RemoteKey.MEDIA_PLAY_PAUSE),
            **media_common,
        )
        self._btn_play_pause.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self._btn_fast_forward = ctk.CTkButton(
            media_row,
            text="►►",
            command=lambda: self._send_key(RemoteKey.MEDIA_FAST_FORWARD),
            **media_common,
        )
        self._btn_fast_forward.pack(side="left", fill="x", expand=True)

        # 8. Volume Row: Vol -, Mudo, Vol +
        vol_row = ctk.CTkFrame(self._root, fg_color="transparent")
        vol_row.pack(fill="x", padx=12, pady=4)

        self._btn_vol_down = RepeatButton(
            vol_row,
            text="Vol -",
            command=lambda: self._send_key(RemoteKey.VOLUME_DOWN),
            **btn_common,
        )
        self._btn_vol_down.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self._btn_mute = ctk.CTkButton(
            vol_row,
            text="Mudo",
            command=lambda: self._send_key(RemoteKey.MUTE),
            **btn_common,
        )
        self._btn_mute.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self._btn_vol_up = RepeatButton(
            vol_row,
            text="Vol +",
            command=lambda: self._send_key(RemoteKey.VOLUME_UP),
            **btn_common,
        )
        self._btn_vol_up.pack(side="left", fill="x", expand=True)

        # 9. App Shortcuts Container
        self._shortcuts_frame = ctk.CTkFrame(self._root, fg_color="transparent")
        self._shortcuts_frame.pack(fill="x", padx=12, pady=4)
        self.refresh_app_shortcuts()

        # 10. Text Input Row
        text_row = ctk.CTkFrame(self._root, fg_color="transparent")
        text_row.pack(fill="x", padx=12, pady=(4, 12))

        self._text_var = tk.StringVar()
        self._txt_input = ctk.CTkEntry(
            text_row,
            textvariable=self._text_var,
            placeholder_text="Digitar na TV…",
            fg_color=("#f4f4f5", "#27272a"),
            border_color=("#d4d4d8", "#3f3f46"),
            text_color=("#18181b", "#f4f4f5"),
            corner_radius=8,
            height=34,
            font=("Liberation Sans", 11),
        )
        self._txt_input.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._txt_input.bind("<Return>", lambda _e: self._on_send_text())

        self._btn_send_text = ctk.CTkButton(
            text_row,
            text="Enviar",
            width=70,
            height=34,
            corner_radius=8,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=("Liberation Sans", 11, "bold"),
            command=self._on_send_text,
        )
        self._btn_send_text.pack(side="right")

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

    def _show_options_menu(self) -> None:
        """Display options dropdown menu under settings button."""
        x = self._btn_menu.winfo_rootx()
        y = self._btn_menu.winfo_rooty() + self._btn_menu.winfo_height() + 2
        self._menu.post(x, y)

    def _setup_event_subscriptions(self) -> None:
        self._event_bus.on_state(self._on_state_event)
        self._event_bus.on_volume(self._on_volume_event)
        self._event_bus.on_current_app(self._on_current_app_event)
        self._event_bus.on_error(self._on_error_event)

    def _load_saved_tvs(self) -> None:
        self._tvs = self._config_store.list_tvs()
        names = [tv.name for tv in self._tvs]
        if names:
            self._tv_selector.configure(values=names)
        else:
            self._tv_selector.configure(values=["Nenhuma TV cadastrada"])

        last_id = self._config_store.get_last_selected_id()
        selected_index = -1
        if last_id:
            for idx, tv in enumerate(self._tvs):
                if tv.id == last_id:
                    selected_index = idx
                    break

        if selected_index >= 0:
            target = self._tvs[selected_index]
            self._tv_selector.set(target.name)
            self._selected_tv_id = target.id
            self._connect_to_selected_tv()
        elif self._tvs:
            target = self._tvs[0]
            self._tv_selector.set(target.name)
            self._selected_tv_id = target.id
            self._connect_to_selected_tv()
        else:
            self._tv_selector.set("Nenhuma TV cadastrada")

    def refresh_tvs(self, selected_tv_id: str | None = None) -> None:
        """Reload the list of saved TVs in the selector dropdown."""
        self._tvs = self._config_store.list_tvs()
        names = [tv.name for tv in self._tvs]
        if names:
            self._tv_selector.configure(values=names)
        else:
            self._tv_selector.configure(values=["Nenhuma TV cadastrada"])

        last_id = self._config_store.get_last_selected_id()
        target_id = selected_tv_id or self._selected_tv_id or last_id
        selected_idx = -1
        if target_id:
            for idx, tv in enumerate(self._tvs):
                if tv.id == target_id:
                    selected_idx = idx
                    break

        if selected_idx >= 0:
            target = self._tvs[selected_idx]
            self._tv_selector.set(target.name)
            self._selected_tv_id = target.id
        elif self._tvs:
            target = self._tvs[0]
            self._tv_selector.set(target.name)
            self._selected_tv_id = target.id
        else:
            self._tv_selector.set("Nenhuma TV cadastrada")
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
            btn = ctk.CTkButton(
                self._shortcuts_frame,
                text=item.label,
                fg_color=("#e4e4e7", "#27272a"),
                hover_color=("#d4d4d8", "#3f3f46"),
                text_color=("#18181b", "#f4f4f5"),
                font=("Liberation Sans", 10, "bold"),
                corner_radius=8,
                height=30,
                border_width=1,
                border_color=("#d4d4d8", "#3f3f46"),
                command=self._make_launch_handler(link_target),
            )
            btn.pack(side="left", fill="x", expand=True, padx=2)

    def _make_launch_handler(self, link: str) -> Callable[[], None]:
        return lambda: self._session.launch_app(link)

    def _on_tv_option_selected(self, chosen_name: str) -> None:
        for tv in self._tvs:
            if tv.name == chosen_name:
                self._selected_tv_id = tv.id
                self._connect_to_selected_tv()
                break

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
            self._pairing_banner.pack(fill="x", padx=12, pady=2, before=self._status_bar)
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
        btn_state = "normal" if connected else "disabled"

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
            btn.configure(state=btn_state)

        for child in self._shortcuts_frame.winfo_children():
            if isinstance(child, ctk.CTkButton):
                child.configure(state=btn_state)

        # Power button remains clickable anytime so user can trigger WoL or reconnect
        self._btn_power.configure(state="normal")
