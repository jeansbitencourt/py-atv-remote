"""Qt preview configuration tests with no network access."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

from PyQt6 import QtWidgets

from py_atv_remote.domain.models import TvProfile
from py_atv_remote.infrastructure.config_store import ConfigStore
from py_atv_remote.infrastructure.paths import AppPaths
from py_atv_remote.services.events import DirectDispatcher
from py_atv_remote.ui.preview_dialog import PreviewDialog


def test_disabled_by_default_and_confirmation_required(tmp_path: Path) -> None:
    qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    parent = QtWidgets.QWidget()
    store = ConfigStore(AppPaths(base_dir=tmp_path))
    profile = TvProfile("tv", "Sala", "192.168.1.5")
    store.save_tv(profile)
    dialog = PreviewDialog(parent, profile, store, MagicMock(), DirectDispatcher())
    assert not dialog.enabled.isChecked()
    dialog.enabled.setChecked(True)
    dialog.endpoint.setText("192.168.1.5:3456")
    dialog._save()
    assert not store.get_preview_settings("tv").enabled
    assert "confirmar" in dialog.status.text()
    dialog._verified_endpoint = dialog.endpoint.text()
    dialog._identity = "unique"
    dialog._save()
    assert store.get_preview_settings("tv").identity == "unique"
    dialog.close()
    parent.close()
    qapp.processEvents()


def test_legacy_mode_and_cancel_clear_secret(tmp_path: Path) -> None:
    qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    parent = QtWidgets.QWidget()
    store = ConfigStore(AppPaths(base_dir=tmp_path))
    dialog = PreviewDialog(
        parent, TvProfile("tv", "Sala", "192.168.1.5"), store, MagicMock(), DirectDispatcher()
    )
    dialog.mode.setCurrentIndex(1)
    assert dialog.endpoint.text() == "192.168.1.5:5555"
    assert not dialog.code.isEnabled()
    dialog.code.setText("123456")
    dialog.reject()
    assert dialog.code.text() == ""
    assert not dialog._alive
    parent.close()
    qapp.processEvents()
