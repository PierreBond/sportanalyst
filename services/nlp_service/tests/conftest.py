from __future__ import annotations

import pytest
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
src_path = project_root / "services" / "nlp_service" / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


@pytest.fixture
def sample_team_id() -> str:
    """Sample team ID for testing."""
    return "team_arsenal"


@pytest.fixture
def sample_player_id() -> str:
    """Sample player ID for testing."""
    return "player_1"


@pytest.fixture
def sample_entity_ids(sample_team_id, sample_player_id) -> list[str]:
    """Sample entity IDs for testing."""
    return [sample_team_id, sample_player_id]
