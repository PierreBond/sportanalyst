from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
for p in [
    str(project_root / "libs"),
    str(project_root / "services" / "nlp_service" / "src"),
]:
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest


@pytest.fixture
def sample_team_id() -> str:
    return "team_arsenal"


@pytest.fixture
def sample_player_id() -> str:
    return "player_1"


@pytest.fixture
def sample_entity_ids(sample_team_id: str, sample_player_id: str) -> list[str]:
    return [sample_team_id, sample_player_id]
