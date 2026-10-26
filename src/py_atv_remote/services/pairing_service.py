"""Pairing service orchestrating mTLS certificate generation and PIN verification."""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from androidtvremote2 import (
    AndroidTVRemote,
    CannotConnect,
    ConnectionClosed,
    InvalidAuth,
)

from py_atv_remote.domain.errors import (
    InvalidPinError,
    PairingFailedError,
    TvUnreachableError,
)
from py_atv_remote.domain.models import DiscoveredTv, TvProfile
from py_atv_remote.infrastructure.cert_store import CertStore
from py_atv_remote.infrastructure.config_store import ConfigStore
from py_atv_remote.infrastructure.mdns_browser import normalize_mac_or_id

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class PairingSession:
    """Represents an active in-flight pairing handshake."""

    tv_id: str
    target_name: str
    host: str
    api_port: int
    pair_port: int
    model: str | None
    client: AndroidTVRemote
    newly_generated_cert: bool


class PairingService:
    """Manages initiating pairing, verifying PIN code, and saving credentials."""

    def __init__(
        self,
        config_store: ConfigStore,
        cert_store: CertStore,
    ) -> None:
        self._config_store = config_store
        self._cert_store = cert_store

    async def start_pairing(
        self,
        target: DiscoveredTv | TvProfile,
    ) -> PairingSession:
        """Initiate pairing with a TV, triggering the PIN prompt on its screen."""
        host = target.host
        api_port = target.api_port if isinstance(target, TvProfile) else target.port
        pair_port = target.pair_port if isinstance(target, TvProfile) else 6467
        client_name = self._config_store.get_client_name()

        # Temporary ID if target has none yet (e.g. manual IP)
        provisional_id = target.id or normalize_mac_or_id(host) or "new_tv"

        certfile = str(self._cert_store.get_cert_path(provisional_id))
        keyfile = str(self._cert_store.get_key_path(provisional_id))

        client = AndroidTVRemote(
            client_name=client_name,
            certfile=certfile,
            keyfile=keyfile,
            host=host,
            api_port=api_port,
            pair_port=pair_port,
        )

        had_certs = self._cert_store.has_certs(provisional_id)
        await client.async_generate_cert_if_missing()
        newly_generated = not had_certs

        # Query TV name and canonical MAC address from TV's certificate
        model: str | None = None
        canonical_id: str = provisional_id
        try:
            tv_model, tv_mac = await client.async_get_name_and_mac()
            model = tv_model
            normalized_mac = normalize_mac_or_id(tv_mac)
            if normalized_mac:
                canonical_id = normalized_mac
        except CannotConnect as exc:
            if newly_generated:
                self._cert_store.delete_certs(provisional_id)
            raise TvUnreachableError(f"Cannot reach Android TV at {host}:{pair_port}") from exc

        # If canonical ID differs from provisional ID, rename cert files to match
        if canonical_id != provisional_id:
            old_cert = self._cert_store.get_cert_path(provisional_id)
            old_key = self._cert_store.get_key_path(provisional_id)
            new_cert = self._cert_store.get_cert_path(canonical_id)
            new_key = self._cert_store.get_key_path(canonical_id)
            if old_cert.exists():
                old_cert.replace(new_cert)
            if old_key.exists():
                old_key.replace(new_key)

            client = AndroidTVRemote(
                client_name=client_name,
                certfile=str(new_cert),
                keyfile=str(new_key),
                host=host,
                api_port=api_port,
                pair_port=pair_port,
            )

        try:
            await client.async_start_pairing()
            LOGGER.info("Pairing initiated for TV %s (%s at %s)", target.name, canonical_id, host)
        except (CannotConnect, ConnectionClosed, OSError) as exc:
            if newly_generated:
                self._cert_store.delete_certs(canonical_id)
            raise PairingFailedError(f"Failed to start pairing with TV at {host}: {exc}") from exc

        return PairingSession(
            tv_id=canonical_id,
            target_name=target.name,
            host=host,
            api_port=api_port,
            pair_port=pair_port,
            model=model,
            client=client,
            newly_generated_cert=newly_generated,
        )

    async def finish_pairing(
        self,
        session: PairingSession,
        pairing_code: str,
    ) -> TvProfile:
        """Complete pairing by submitting the PIN displayed on the TV."""
        cleaned_pin = pairing_code.strip().upper()
        if not cleaned_pin:
            raise InvalidPinError("PIN cannot be empty.")

        try:
            await session.client.async_finish_pairing(cleaned_pin)
            LOGGER.info("Pairing succeeded for TV %s (%s)", session.target_name, session.tv_id)
        except InvalidAuth as exc:
            raise InvalidPinError("Invalid PIN entered. Please verify and try again.") from exc
        except (ConnectionClosed, CannotConnect, OSError) as exc:
            raise PairingFailedError(f"Pairing connection terminated: {exc}") from exc

        # Secure certificate permissions
        self._cert_store.secure_permissions(session.tv_id)

        # Create or update TvProfile
        existing = self._config_store.get_tv(session.tv_id)
        name = existing.name if existing else session.target_name
        # If name is generic fallback like "Android TV (IP)", prefer model or instance name
        if name.startswith("Android TV (") and session.model:
            name = session.model

        profile = TvProfile(
            id=session.tv_id,
            name=name,
            host=session.host,
            api_port=session.api_port,
            pair_port=session.pair_port,
            model=session.model or (existing.model if existing else None),
            wol_mac=existing.wol_mac if existing else None,
            paired_at=datetime.now(UTC),
        )
        self._config_store.save_tv(profile)
        return profile

    def cancel_pairing(self, session: PairingSession) -> None:
        """Cancel an in-progress pairing session and clean up temporary certs if uncompleted."""
        with contextlib.suppress(Exception):
            session.client.disconnect()

        if session.newly_generated_cert and not self._config_store.get_tv(session.tv_id):
            self._cert_store.delete_certs(session.tv_id)
        LOGGER.info("Pairing session cancelled for TV %s", session.tv_id)
