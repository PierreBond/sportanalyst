from __future__ import annotations

import sys
from pathlib import Path

import pytest


def pytest_configure(config: pytest.Config) -> None:
    project_root = Path(__file__).parent.parent.parent
    for p in [
        str(project_root / "libs"),
        str(project_root / "services" / "model_serving" / "src"),
    ]:
        if p not in sys.path:
            sys.path.insert(0, p)


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
