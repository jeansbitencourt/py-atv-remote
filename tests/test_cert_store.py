"""Tests for certificate storage."""

from pathlib import Path

from py_atv_remote.infrastructure.cert_store import CertStore
from py_atv_remote.infrastructure.paths import AppPaths


def test_cert_store_lifecycle(tmp_path: Path) -> None:
    paths = AppPaths(base_dir=tmp_path)
    store = CertStore(paths)
    tv_id = "84c8a02b914c"

    assert not store.has_certs(tv_id)

    cert_p = store.get_cert_path(tv_id)
    key_p = store.get_key_path(tv_id)

    cert_p.write_text("CERT_CONTENT")
    assert not store.has_certs(tv_id)  # key is missing

    key_p.write_text("KEY_CONTENT")
    assert store.has_certs(tv_id)

    store.secure_permissions(tv_id)
    assert (cert_p.stat().st_mode & 0o777) == 0o600
    assert (key_p.stat().st_mode & 0o777) == 0o600

    store.delete_certs(tv_id)
    assert not store.has_certs(tv_id)
    assert not cert_p.exists()
    assert not key_p.exists()
