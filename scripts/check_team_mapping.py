"""Verify every upcoming fixture's team name resolves to a model team class.

Imports the real resolver from sports_common.team_map (shared with the API
and batch_predict) so it always tests the actual mapping.

Usage: DATABASE_URL_SYNC=postgresql://... python scripts/check_team_mapping.py
"""
import json
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

# allow running without the package pip-installed (libs/ lives in the repo)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "libs"))
from sports_common.team_map import remove_accents, resolve_team_name  # noqa: E402

BASE = Path(__file__).resolve().parent.parent


def main() -> int:
    known = set(json.load(open(BASE / "models/predictor_metadata.json"))["team_classes"])

    engine = create_engine(os.environ["DATABASE_URL_SYNC"])
    rows = engine.connect().execute(text("""
        SELECT DISTINCT t.name FROM matches m
        JOIN teams t ON t.team_id IN (m.home_team_id, m.away_team_id)
        WHERE m.status = 'scheduled' AND m.scheduled_at >= NOW()
    """)).fetchall()
    names = sorted({r[0] for r in rows})

    resolved, unresolved, novel = [], [], []
    for n in names:
        r = resolve_team_name(n, known)
        (resolved if r in known else unresolved).append(n)
        if r not in known and not any(remove_accents(k).lower() in remove_accents(n).lower()
                                      for k in known):
            novel.append(n)

    print(f"{len(names)} distinct teams on upcoming fixtures")
    print(f"  {len(resolved)} resolved to a model team class")
    print(f"  {len(unresolved)} unresolved ({len(novel)} look absent from model entirely)")
    if unresolved:
        print("  unresolved:", ", ".join(unresolved))

    # Fail only if a team the model knows (substring match) failed to resolve.
    broken = [n for n in unresolved if n not in novel]
    if broken:
        print(f"\nFAIL: model-known teams not resolving: {broken}")
        return 1
    print("\nOK: every model-known team resolves")
    return 0


if __name__ == "__main__":
    sys.exit(main())
