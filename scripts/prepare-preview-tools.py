"""Prepare the pinned upstream toolchain for a local Linux preview build."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "packaging" / "preview-tools.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, nargs="?", help="Official scrcpy release archive")
    parser.add_argument("--download", action="store_true", help="Download pinned official release")
    args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        parser.error("This toolchain supports Linux x86_64 only")
    manifest = json.loads(MANIFEST.read_text())
    if bool(args.archive) == args.download:
        parser.error("Specify an archive or --download")
    archive_path = args.archive
    if args.download:
        cache = ROOT / "build" / "preview-tools"
        cache.mkdir(parents=True, exist_ok=True)
        archive_path = cache / (manifest["directory"] + ".tar.gz")
        if (
            not archive_path.exists()
            or hashlib.sha256(archive_path.read_bytes()).hexdigest() != manifest["sha256"]
        ):
            print(f"Downloading {manifest['url']}", flush=True)
            try:
                with tempfile.NamedTemporaryFile(dir=cache, delete=False) as download:
                    temporary_path = Path(download.name)
                    try:
                        with urllib.request.urlopen(manifest["url"], timeout=60) as response:
                            shutil.copyfileobj(response, download)
                        download.flush()
                        if (
                            hashlib.sha256(temporary_path.read_bytes()).hexdigest()
                            != manifest["sha256"]
                        ):
                            parser.error("Downloaded archive SHA-256 mismatch")
                        temporary_path.replace(archive_path)
                    finally:
                        temporary_path.unlink(missing_ok=True)
            except OSError as exc:
                parser.error(f"Could not download official release: {exc}")
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    if digest != manifest["sha256"]:
        parser.error("Archive SHA-256 does not match the pinned official release")
    target = ROOT / "src" / "py_atv_remote" / "vendor" / "linux-x86_64"
    with tempfile.TemporaryDirectory() as temporary:
        staging = Path(temporary)
        with tarfile.open(archive_path) as archive:
            archive.extractall(staging, filter="data")
        source = staging / manifest["directory"]
        for name in ("adb", "scrcpy", "scrcpy-server", "LICENSE"):
            if not (source / name).is_file():
                parser.error(f"Missing release component: {name}")
        target.mkdir(parents=True, exist_ok=True)
        for item in source.iterdir():
            if item.is_file():
                shutil.copy2(item, target / item.name)
        shutil.copy2(MANIFEST, target / "manifest.json")
    print(f"Prepared verified tools in {target}")
    print("Local validation build only; see packaging/PREVIEW_DISTRIBUTION.md before publication.")


if __name__ == "__main__":
    main()
