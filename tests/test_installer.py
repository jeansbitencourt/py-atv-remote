"""Exercise installer orchestration without changing the user's installation."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def fake_installer(tmp_path: Path) -> tuple[dict[str, str], Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "commands.jsonl"
    fake_uv = bin_dir / "uv"
    fake_uv.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['INSTALL_LOG'], 'a') as log:\n"
        " entry = {'args': args, 'plain': os.environ.get('PY_ATV_REMOTE_NO_BUNDLED')}\n"
        " log.write(json.dumps(entry) + '\\n')\n"
        "if args[0] == 'build':\n"
        " out = pathlib.Path(args[args.index('--out-dir') + 1]); out.mkdir()\n"
        " (out / 'test.whl').write_text('placeholder')\n"
        "elif args[:3] == ['tool', 'dir', '--bin']:\n"
        " print(os.environ['INSTALL_BIN'])\n"
        "elif args[0] == 'run' and '-' in args:\n"
        " index = args.index('-')\n"
        " os.execv(sys.executable, [sys.executable] + args[index:])\n"
    )
    fake_uv.chmod(0o700)
    environment = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "HOME": str(tmp_path / "home"),
        "XDG_DATA_HOME": str(tmp_path / "desktop data"),
        "INSTALL_LOG": str(log),
        "INSTALL_BIN": str(tmp_path / "user bin"),
    }
    return environment, log


def test_default_installer_prepares_builds_and_installs(
    fake_installer: tuple[dict[str, str], Path],
) -> None:
    environment, log = fake_installer
    subprocess.run(
        ["bash", str(ROOT / "scripts/install-desktop.sh")],
        env=environment,
        check=True,
        capture_output=True,
    )
    commands = [json.loads(line) for line in log.read_text().splitlines()]
    assert any("--download" in item["args"] for item in commands)
    assert any(item["args"][0] == "build" for item in commands)
    assert any(item["args"][:2] == ["tool", "install"] for item in commands)
    desktop = Path(environment["XDG_DATA_HOME"]) / "applications/py-atv-remote.desktop"
    assert f'Exec="{environment["INSTALL_BIN"]}/py-atv-remote"' in desktop.read_text()


def test_plain_installer_never_downloads_preview(
    fake_installer: tuple[dict[str, str], Path],
) -> None:
    environment, log = fake_installer
    subprocess.run(
        ["bash", str(ROOT / "scripts/install-desktop.sh"), "--without-preview"],
        env=environment,
        check=True,
        capture_output=True,
    )
    commands = [json.loads(line) for line in log.read_text().splitlines()]
    assert not any("--download" in item["args"] for item in commands)
    assert next(item for item in commands if item["args"][0] == "build")["plain"] == "1"


def test_installer_rejects_missing_wheel_before_install(
    fake_installer: tuple[dict[str, str], Path],
) -> None:
    environment, log = fake_installer
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/install-desktop.sh"), "/missing.whl"],
        env=environment,
        capture_output=True,
    )
    assert result.returncode != 0
    assert not log.exists()
