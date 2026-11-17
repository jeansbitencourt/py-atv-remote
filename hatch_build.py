"""Mark builds containing optional native tools as platform-specific wheels."""

import os
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        vendor = Path(self.root) / "src" / "py_atv_remote" / "vendor"
        if (
            vendor.is_dir()
            and self.target_name == "wheel"
            and os.environ.get("PY_ATV_REMOTE_NO_BUNDLED") != "1"
        ):
            build_data["pure_python"] = False
            build_data["tag"] = "py3-none-linux_x86_64"
            build_data["force_include"][str(vendor)] = "py_atv_remote/vendor"
