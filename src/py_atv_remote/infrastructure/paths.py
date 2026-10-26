"""Path resolution and directory creation following XDG Base Directory Specification."""

from __future__ import annotations

import os
from pathlib import Path


class AppPaths:
    """Manages application paths in the user's home directory."""

    def __init__(self, base_dir: Path | None = None) -> None:
        if base_dir is not None:
            self._config_dir = Path(base_dir).resolve()
        else:
            xdg_config = os.environ.get("XDG_CONFIG_HOME")
            if xdg_config and xdg_config.strip():
                self._config_dir = Path(xdg_config) / "py-atv-remote"
            else:
                self._config_dir = Path.home() / ".config" / "py-atv-remote"

        self._certs_dir = self._config_dir / "certs"
        self.ensure_dirs()

    @property
    def config_dir(self) -> Path:
        """Return the root configuration directory."""
        return self._config_dir

    @property
    def certs_dir(self) -> Path:
        """Return the directory storing mTLS certificates."""
        return self._certs_dir

    @property
    def config_file(self) -> Path:
        """Return the main config.json file path."""
        return self._config_dir / "config.json"

    def cert_file(self, tv_id: str) -> Path:
        """Return the path to the certificate file for the specified TV."""
        clean_id = self._normalize_id(tv_id)
        return self._certs_dir / f"cert_{clean_id}.pem"

    def key_file(self, tv_id: str) -> Path:
        """Return the path to the private key file for the specified TV."""
        clean_id = self._normalize_id(tv_id)
        return self._certs_dir / f"key_{clean_id}.pem"

    def ensure_dirs(self) -> None:
        """Ensure directories exist with secure permissions (0700)."""
        self._config_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._certs_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Ensure mode 0700 if they already existed with broader perms
        try:
            self._config_dir.chmod(0o700)
            self._certs_dir.chmod(0o700)
        except OSError:
            pass

    @staticmethod
    def _normalize_id(tv_id: str) -> str:
        """Normalize an ID string for safe usage in file paths."""
        return "".join(c for c in tv_id.lower() if c.isalnum() or c in ("-", "_"))
