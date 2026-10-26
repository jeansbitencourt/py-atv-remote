"""Storage and lifecycle management for per-TV mTLS certificates and keys."""

from __future__ import annotations

import logging
from pathlib import Path

from py_atv_remote.infrastructure.paths import AppPaths

LOGGER = logging.getLogger(__name__)


class CertStore:
    """Manages certificates and private keys on disk."""

    def __init__(self, paths: AppPaths) -> None:
        self._paths = paths

    def get_cert_path(self, tv_id: str) -> Path:
        """Return path to the public certificate for a TV."""
        return self._paths.cert_file(tv_id)

    def get_key_path(self, tv_id: str) -> Path:
        """Return path to the private key for a TV."""
        return self._paths.key_file(tv_id)

    def has_certs(self, tv_id: str) -> bool:
        """Return True if both certificate and private key files exist and are non-empty."""
        cert_p = self.get_cert_path(tv_id)
        key_p = self.get_key_path(tv_id)
        return (
            cert_p.is_file()
            and cert_p.stat().st_size > 0
            and key_p.is_file()
            and key_p.stat().st_size > 0
        )

    def secure_permissions(self, tv_id: str) -> None:
        """Set 0600 permissions on existing certificate and private key files."""
        for path in (self.get_cert_path(tv_id), self.get_key_path(tv_id)):
            if path.exists():
                try:
                    path.chmod(0o600)
                except OSError as exc:
                    LOGGER.warning("Could not set 0600 permissions on %s: %s", path, exc)

    def delete_certs(self, tv_id: str) -> None:
        """Remove certificate and private key files for the given TV."""
        for path in (self.get_cert_path(tv_id), self.get_key_path(tv_id)):
            if path.exists():
                try:
                    path.unlink()
                    LOGGER.info("Deleted certificate file %s", path)
                except OSError as exc:
                    LOGGER.warning("Could not delete %s: %s", path, exc)
