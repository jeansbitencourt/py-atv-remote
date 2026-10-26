"""Device manager dialog for listing, discovering, renaming, and pairing TVs."""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, simpledialog, ttk

from py_atv_remote.domain.errors import TvUnreachableError
from py_atv_remote.domain.models import DiscoveredTv, TvProfile
from py_atv_remote.infrastructure.cert_store import CertStore
from py_atv_remote.infrastructure.config_store import ConfigStore
from py_atv_remote.services.async_runner import AsyncRunner
from py_atv_remote.services.discovery_service import DiscoveryService
from py_atv_remote.services.events import EventBus
from py_atv_remote.services.pairing_service import PairingService, PairingSession
from py_atv_remote.services.remote_session import RemoteSessionService
from py_atv_remote.ui.pair_dialog import PairDialog

LOGGER = logging.getLogger(__name__)


class DeviceManager(tk.Toplevel):
    """Dialog allowing users to view discovered TVs, pair new devices, and manage saved profiles."""

    def __init__(
        self,
        parent: tk.Tk | tk.Toplevel,
        config_store: ConfigStore,
        cert_store: CertStore,
        discovery_service: DiscoveryService,
        pairing_service: PairingService,
        remote_session: RemoteSessionService,
        event_bus: EventBus,
        async_runner: AsyncRunner,
        on_tv_selected: Callable[[str], None],
    ) -> None:
        super().__init__(parent)
        self._config_store = config_store
        self._cert_store = cert_store
        self._discovery = discovery_service
        self._pairing = pairing_service
        self._session = remote_session
        self._event_bus = event_bus
        self._runner = async_runner
        self._on_tv_selected = on_tv_selected

        self.title("Gerenciador de Android TVs")
        self.transient(parent)
        self.minsize(620, 380)

        # Cache of rows: item_key -> DiscoveredTv | TvProfile
        self._items: dict[str, DiscoveredTv | TvProfile] = {}

        self._build_ui()
        self._setup_events()
        self._refresh_list()

    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self, padding=12)
        main_frame.pack(fill=tk.BOTH, expand=True)

        header_lbl = ttk.Label(
            main_frame,
            text="TVs Encontradas na Rede e Cadastradas",
            font=("sans-serif", 11, "bold"),
        )
        header_lbl.pack(anchor=tk.W, pady=(0, 8))

        # Treeview table
        columns = ("name", "host", "status", "id")
        self._tree = ttk.Treeview(
            main_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=10,
        )
        self._tree.heading("name", text="Nome")
        self._tree.heading("host", text="Endereço IP")
        self._tree.heading("status", text="Status")
        self._tree.heading("id", text="ID / MAC")

        self._tree.column("name", width=190)
        self._tree.column("host", width=120)
        self._tree.column("status", width=150)
        self._tree.column("id", width=120)

        tree_scroll = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=tree_scroll.set)

        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        # Right Action Buttons Panel
        btn_panel = ttk.Frame(main_frame)
        btn_panel.pack(side=tk.RIGHT, fill=tk.Y)

        self._btn_use = ttk.Button(btn_panel, text="Usar esta TV", command=self._on_use_clicked)
        self._btn_use.pack(fill=tk.X, pady=(0, 6))

        self._btn_pair = ttk.Button(btn_panel, text="Parear TV…", command=self._on_pair_clicked)
        self._btn_pair.pack(fill=tk.X, pady=(0, 6))

        self._btn_rename = ttk.Button(btn_panel, text="Renomear…", command=self._on_rename_clicked)
        self._btn_rename.pack(fill=tk.X, pady=(0, 6))

        self._btn_forget = ttk.Button(
            btn_panel,
            text="Esquecer TV",
            command=self._on_forget_clicked,
        )
        self._btn_forget.pack(fill=tk.X, pady=(0, 14))

        self._btn_add_ip = ttk.Button(
            btn_panel,
            text="Adicionar por IP…",
            command=self._on_add_ip_clicked,
        )
        self._btn_add_ip.pack(fill=tk.X, pady=(0, 6))

        self._btn_scan = ttk.Button(
            btn_panel,
            text="Varredura Completa",
            command=self._on_scan_clicked,
        )
        self._btn_scan.pack(fill=tk.X, pady=(0, 6))

        self._status_var = tk.StringVar(value="Varredura mDNS ativa em segundo plano.")
        status_lbl = ttk.Label(self, textvariable=self._status_var, padding=(12, 4))
        status_lbl.pack(side=tk.BOTTOM, fill=tk.X)

        self._tree.bind("<Double-1>", lambda _e: self._on_double_click())

    def _setup_events(self) -> None:
        self._unsub_disc = self._event_bus.on_tv_discovered(lambda _tv: self._refresh_list())
        self._unsub_disp = self._event_bus.on_tv_disappeared(lambda _id: self._refresh_list())

        def _cleanup() -> None:
            self._unsub_disc()
            self._unsub_disp()
            self.destroy()

        self.protocol("WM_DELETE_WINDOW", _cleanup)

    def _refresh_list(self) -> None:
        """Combine saved profiles and live discovered devices into the view."""
        self._tree.delete(*self._tree.get_children())
        self._items.clear()

        saved_tvs = {tv.id: tv for tv in self._config_store.list_tvs()}
        discovered_tvs = {tv.id or tv.host: tv for tv in self._discovery.discovered_tvs}

        # 1. Add saved TVs
        for tv_id, profile in saved_tvs.items():
            disc = discovered_tvs.get(tv_id)
            has_certs = self._cert_store.has_certs(tv_id)

            if not has_certs:
                status = "Pareamento Pendente"
            elif self._session.current_profile and self._session.current_profile.id == tv_id:
                status = f"Ativa ({self._session.state.value})"
            elif disc is not None:
                status = "Na rede (Standby)" if disc.in_standby else "Na rede (Online)"
            else:
                status = "Cadastrada (Offline)"

            host = disc.host if disc else profile.host
            item_id = f"saved_{tv_id}"
            self._items[item_id] = profile
            self._tree.insert("", tk.END, iid=item_id, values=(profile.name, host, status, tv_id))

        # 2. Add un-paired discovered TVs
        for disc_key, disc_tv in discovered_tvs.items():
            if disc_tv.id and disc_tv.id in saved_tvs:
                continue

            status = "Nova TV encontrada"
            if disc_tv.in_standby:
                status = "Nova (Standby)"

            item_id = f"disc_{disc_key}"
            self._items[item_id] = disc_tv
            self._tree.insert(
                "",
                tk.END,
                iid=item_id,
                values=(disc_tv.name, disc_tv.host, status, disc_tv.id or "-"),
            )

    def _get_selected_item(self) -> DiscoveredTv | TvProfile | None:
        selection = self._tree.selection()
        if not selection:
            return None
        return self._items.get(selection[0])

    def _on_use_clicked(self) -> None:
        item = self._get_selected_item()
        if not item:
            messagebox.showinfo("Seleção", "Selecione uma TV na lista para usar.", parent=self)
            return

        if isinstance(item, TvProfile):
            self._on_tv_selected(item.id)
            self.destroy()
        else:
            # Unpaired discovered TV
            res = messagebox.askyesno(
                "Pareamento Necessário",
                f"A TV '{item.name}' ainda não está pareada. Deseja pareá-la agora?",
                parent=self,
            )
            if res:
                self._start_pairing_flow(item)

    def _on_double_click(self) -> None:
        self._on_use_clicked()

    def _on_pair_clicked(self) -> None:
        item = self._get_selected_item()
        if not item:
            messagebox.showinfo("Seleção", "Selecione uma TV na lista para parear.", parent=self)
            return
        self._start_pairing_flow(item)

    def _start_pairing_flow(self, target: DiscoveredTv | TvProfile) -> None:
        self._status_var.set(f"Iniciando pareamento com {target.name}…")

        async def _do_start() -> None:
            try:
                session = await self._pairing.start_pairing(target)
                self._runner.call_soon(lambda: self._open_pair_dialog(session))
            except TvUnreachableError as exc:
                err_text = str(exc)
                self._runner.call_soon(
                    lambda: messagebox.showerror("TV Inacessível", err_text, parent=self)
                )
            except Exception as exc:
                err_text = str(exc)
                self._runner.call_soon(
                    lambda: messagebox.showerror("Erro de Pareamento", err_text, parent=self)
                )
            finally:
                self._runner.call_soon(
                    lambda: self._status_var.set("Varredura mDNS ativa em segundo plano.")
                )

        self._runner.submit(_do_start())

    def _open_pair_dialog(self, session: PairingSession) -> None:
        PairDialog(
            parent=self,
            pairing_service=self._pairing,
            pairing_session=session,
            async_runner=self._runner,
            on_success=self._on_pair_success,
        )

    def _on_pair_success(self, profile: TvProfile) -> None:
        self._refresh_list()
        messagebox.showinfo(
            "Sucesso",
            f"A TV '{profile.name}' foi pareada com sucesso!",
            parent=self,
        )
        self._on_tv_selected(profile.id)
        self.destroy()

    def _on_rename_clicked(self) -> None:
        item = self._get_selected_item()
        if not isinstance(item, TvProfile):
            msg = "Selecione uma TV já cadastrada para renomear."
            messagebox.showinfo("Renomear", msg, parent=self)
            return

        new_name = simpledialog.askstring(
            "Renomear TV",
            f"Novo nome para '{item.name}':",
            initialvalue=item.name,
            parent=self,
        )
        if new_name and new_name.strip():
            updated = item.with_name(new_name.strip())
            self._config_store.save_tv(updated)
            self._refresh_list()
            self._on_tv_selected(updated.id)

    def _on_forget_clicked(self) -> None:
        item = self._get_selected_item()
        if not isinstance(item, TvProfile):
            msg = "Selecione uma TV cadastrada para remover."
            messagebox.showinfo("Esquecer TV", msg, parent=self)
            return

        confirmed = messagebox.askyesno(
            "Confirmar Remoção",
            f"Deseja esquecer e remover os certificados da TV '{item.name}'?\n"
            "Será necessário parear novamente para controlá-la.",
            parent=self,
        )
        if not confirmed:
            return

        if self._session.current_profile and self._session.current_profile.id == item.id:
            self._session.disconnect()

        self._config_store.delete_tv(item.id)
        self._cert_store.delete_certs(item.id)
        self._refresh_list()
        self._on_tv_selected("")

    def _on_add_ip_clicked(self) -> None:
        ip_addr = simpledialog.askstring(
            "Adicionar TV por IP",
            "Digite o endereço IPv4 da Android TV:\n(Ex: 192.168.2.104)",
            parent=self,
        )
        if not ip_addr or not ip_addr.strip():
            return

        host = ip_addr.strip()
        self._status_var.set(f"Verificando {host}:6466…")

        async def _probe() -> None:
            try:
                tv = await self._discovery.probe_manual(host)
                self._runner.call_soon(lambda: self._start_pairing_flow(tv))
            except TvUnreachableError:
                self._runner.call_soon(
                    lambda: messagebox.showerror(
                        "TV Inacessível",
                        f"Não foi possível conectar em {host}:6466.\n"
                        "Verifique se o IP está correto e a TV está ligada na mesma rede Wi-Fi.",
                        parent=self,
                    )
                )
            finally:
                self._runner.call_soon(
                    lambda: self._status_var.set("Varredura mDNS ativa em segundo plano.")
                )

        self._runner.submit(_probe())

    def _on_scan_clicked(self) -> None:
        self._status_var.set("Executando varredura TCP na sub-rede…")
        self._btn_scan["state"] = tk.DISABLED

        async def _do_scan() -> None:
            try:
                await self._discovery.full_scan()
                self._runner.call_soon(self._refresh_list)
            finally:
                self._runner.call_soon(self._on_scan_finished)

        self._runner.submit(_do_scan())

    def _on_scan_finished(self) -> None:
        self._btn_scan["state"] = tk.NORMAL
        self._status_var.set("Varredura concluída.")
