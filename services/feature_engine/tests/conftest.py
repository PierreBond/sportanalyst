from __future__ import annotations

import pytest
import sys
from pathlib import Path


def pytest_configure(config: pytest.Config) -> None:
    project_root = Path(__file__).parent.parent.parent
    src_path = project_root / "services" / "feature_engine" / "src"
    libs_path = project_root / "libs"
    for p in [str(src_path), str(libs_path)]:
        if p not in sys.path:
            sys.path.insert(0, p)


@pytest.fixture
def sample_team_id() -> str:
    return "team_arsenal"


@pytest.fixture
def sample_player_id() -> str:
    return "player_1"


@pytest.fixture
def sample_entity_ids(sample_team_id: str, sample_player_id: str) -> list[str]:
    return [sample_team_id, sample_player_id]
