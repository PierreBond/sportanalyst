from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "libs"))

from sports_common.team_map import canon_team  # noqa: E402


class TestCanonTeam:
    def test_same_club_variants_collapse(self):
        assert canon_team("Brighton & Hove Albion FC") == canon_team("Brighton")
        assert canon_team("Atalanta BC") == canon_team("Atalanta")

    def test_no_repeated_whitespace(self):
        """Token removals used to leave gaps ('real racing     santander')."""
        assert canon_team("Real Racing Club de Santander") == "real racing santander"
        for name in ("Real Racing Club de Santander", "Brighton & Hove Albion FC"):
            assert "  " not in canon_team(name)

    def test_distinct_clubs_stay_distinct(self):
        assert canon_team("Racing Club de Lens") != canon_team("Real Racing Club de Santander")
        assert canon_team("FC Tokyo") != canon_team("Tokyo Verdy")
        assert canon_team("Yokohama FC") != canon_team("Yokohama F. Marinos")

    def test_accents_and_case_are_normalized(self):
        assert canon_team("Real Sociedad de Fútbol") == "real sociedad"
        assert canon_team("FC Internazionale Milano") == "inter"
