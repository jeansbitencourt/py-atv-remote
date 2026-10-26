"""Tests for application paths."""

from pathlib import Path

from py_atv_remote.infrastructure.paths import AppPaths


def test_custom_base_dir(tmp_path: Path) -> None:
    paths = AppPaths(base_dir=tmp_path)
    assert paths.config_dir == tmp_path
    assert paths.certs_dir == tmp_path / "certs"
    assert paths.config_file == tmp_path / "config.json"
    assert paths.certs_dir.is_dir()

    # Permissions on created dirs
    assert (paths.config_dir.stat().st_mode & 0o777) == 0o700
    assert (paths.certs_dir.stat().st_mode & 0o777) == 0o700


def test_cert_and_key_file_paths(tmp_path: Path) -> None:
    paths = AppPaths(base_dir=tmp_path)
    cert_file = paths.cert_file("84:C8:A0:2B:91:4C")
    key_file = paths.key_file("84:C8:A0:2B:91:4C")

    # Normalized name
    assert cert_file.name == "cert_84c8a02b914c.pem"
    assert key_file.name == "key_84c8a02b914c.pem"
    assert cert_file.parent == paths.certs_dir
