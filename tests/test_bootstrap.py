"""Bootstrap and sanity tests."""

import py_atv_remote


def test_package_version() -> None:
    assert py_atv_remote.__version__ == "0.1.0"
