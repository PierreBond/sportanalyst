"""Verify every upcoming fixture's team name resolves to a model team class.

Reads the normalization maps straight from services/model_serving/src/main.py
so it always tests the real constants. Resolution logic mirrors _resolve_team_name.
Exit code 1 if a model-known team fails to resolve.

Usage: DATABASE_URL_SYNC=postgresql://... python scripts/check_team_mapping.py
"""
import ast
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

from sqlalchemy import create_engine, text

BASE = Path(__file__).resolve().parent.parent


def _load_backend_maps() -> dict:
    src = (BASE / "services/model_serving/src/main.py").read_text(encoding="utf-8")
    consts = {}
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name.startswith("_TEAM"):
                consts[name] = ast.literal_eval(node.value)
    return consts


def _remove_accents(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def resolve(db_name: str, known: set[str], maps: dict) -> str | None:
    if not db_name or db_name in known:
        return db_name
    norm = _remove_accents(db_name).lower().strip()
    special = maps["_TEAM_SPECIAL"].get(norm)
    if special and special in known:
        return special
    for p in maps["_TEAM_PREFIXES"]:
        if db_name.startswith(p) and db_name[len(p):] in known:
            return db_name[len(p):]
    for s in maps["_TEAM_SUFFIXES"]:
        if db_name.endswith(s) and db_name[:-len(s)] in known:
            return db_name[:-len(s)]
    for r in maps["_TEAM_REMOVALS"]:
        candidate = db_name.replace(r, "")
        if candidate in known:
            return candidate
    for k in known:
        if _remove_accents(k).lower().strip() == norm:
            return k
    no_numbers = re.sub(r"\b\d+\b", "", norm).strip()
    no_numbers = re.sub(r"\s+", " ", no_numbers)
    for k in known:
        if _remove_accents(k).lower().strip() == no_numbers:
            return k
    return None


def main() -> int:
    maps = _load_backend_maps()
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
        r = resolve(n, known, maps)
        (resolved if r else unresolved).append(n)
        if r is None and not any(_remove_accents(k).lower() in _remove_accents(n).lower()
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
