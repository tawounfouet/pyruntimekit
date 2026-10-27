"""Bootstrap smoke tests for the installed package."""

import pyruntimekit


def test_package_exposes_release_version() -> None:
    assert pyruntimekit.__version__ == "0.1.0a4"
