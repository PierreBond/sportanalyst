from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
libs_path = str(project_root / "libs")
if libs_path not in sys.path:
    sys.path.insert(0, libs_path)

import pytest


def pytest_configure(config: pytest.Config) -> None:
    pass
