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

    def test_token_removal_never_leaves_a_fragment(self):
        """Dropping a club token must not leave a meaningless remainder."""
        assert canon_team("Barcelona B") == "barcelona b"
        assert canon_team("La Coruna") == "la coruna"
        assert canon_team("Man United") == "man united"
        # a real club whose own name is short is still fine
        assert canon_team("AZ Alkmaar") == "az alkmaar"
        assert canon_team("FC Koln") == "koln"

    def test_provider_name_variants_share_one_class(self):
        """The two providers store the same club under different names."""
        assert canon_team("ACF Fiorentina") == canon_team("Fiorentina")
        assert canon_team("OGC Nice") == canon_team("Nice")
        assert canon_team("NEC") == canon_team("NEC Nijmegen")
        assert canon_team("PSV") == canon_team("PSV Eindhoven")
        assert canon_team("AZ") == canon_team("AZ Alkmaar")
        assert canon_team("Olympique Lyonnais") == canon_team("Lyon")
        assert canon_team("Racing Club de Lens") == canon_team("Lens")
        assert canon_team("CA Mineiro") == canon_team("Atletico-MG")
        assert canon_team("Paris FC") == canon_team("Paris Saint Germain")
