"""Backfill historical Pinnacle closing odds (football-data.co.uk CSVs) into odds_snapshots.

Matches CSV rows to DB matches by league + date + exact FT score, then confirms
team names via canon(). Wrong pairings are rejected, not guessed.
Covers: E0/SP1/I1/D1/F1/N1 -> premier_league/la_liga/serie_a/bundesliga/ligue_1/eredivisie.
"""
import difflib
import io
import os
import sys
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pull_odds import canon  # noqa: E402

BASE = "https://football-data.co.uk/mmz4281/{code}/{div}.csv"
LEAGUES = {
    "premier_league": "E0",
    "la_liga": "SP1",
    "serie_a": "I1",
    "bundesliga": "D1",
    "ligue_1": "F1",
    "eredivisie": "N1",
}
SEASONS = {2022: "2223", 2023: "2324", 2024: "2425", 2026: "2627"}
# canon(csv short name) -> canon(DB name); explicit beats fuzzy (two 4-0s can share a day)
ALIASES = {
    "man city": "manchester city",
    "man united": "manchester united",
    "nott m forest": "nottingham forest",
    "spurs": "tottenham",
    "ath madrid": "atletico madrid",
    "ath bilbao": "athletic club",
    "celta": "celta vigo",
    "betis": "real betis",
    "paris sg": "paris saint germain",
    "psg": "paris saint germain",
    "espanol": "espanyol",
    "sheffield united": "sheffield utd",
    "m gladbach": "borussia monchengladbach",
    "gladbach": "borussia monchengladbach",
    "eintracht": "eintracht frankfurt",
    "brest": "stade brestois",
    "st etienne": "saint etienne",
    "verona": "hellas verona",
    "dortmund": "borussia dortmund",
    "hertha": "hertha berlin",
    "troyes": "estac troyes",
}


def fetch_csv(div: str, code: str) -> pd.DataFrame:
    r = httpx.get(BASE.format(code=code, div=div), headers={"User-Agent": "Mozilla/5.0"},
                  timeout=60, follow_redirects=True)
    r.raise_for_status()
    lines = r.text.lstrip("\ufeff").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("Div,"))
    return pd.read_csv(io.StringIO("\n".join(lines[start:])), encoding="latin-1")


def main():
    db = create_engine(os.environ["DATABASE_URL_SYNC"])
    with db.connect() as conn:
        db_rows = conn.execute(text("""
            SELECT m.match_id::text, m.league, m.season, m.scheduled_at,
                   m.home_score, m.away_score, ht.name, at.name
            FROM matches m
            JOIN teams ht ON ht.team_id = m.home_team_id
            JOIN teams at ON at.team_id = m.away_team_id
            WHERE m.status = 'FT' AND m.home_score IS NOT NULL
        """)).fetchall()

    db_idx = {}  # (league, season, date) -> [match tuples]
    for mid, league, season, sched, hs, as_, hn, an in db_rows:
        d = sched.date()
        db_idx.setdefault((league, int(season), d), []).append((mid, hs, as_, hn, an, sched))

    inserted = matched = rejected = 0
    unmatched = []

    for league, div in LEAGUES.items():
        for season, code in SEASONS.items():
            try:
                df = fetch_csv(div, code)
            except Exception as e:
                print(f"{league} {code}: fetch failed: {e}")
                continue
            need = {"Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "PSCH", "PSCD", "PSCA"}
            if not need.issubset(df.columns):
                print(f"{league} {code}: missing odds columns, skipping ({len(df)} rows)")
                continue
            ok = rej = 0
            for _, row in df.iterrows():
                try:
                    d = pd.to_datetime(row["Date"], dayfirst=True).date()
                    hs, as_ = int(row["FTHG"]), int(row["FTAG"])
                    ph, pd_, pa = float(row["PSCH"]), float(row["PSCD"]), float(row["PSCA"])
                except (ValueError, TypeError):
                    continue
                if min(ph, pd_, pa) <= 1.0:
                    continue
                cands = []
                for day_off in range(-2, 3):
                    cands += db_idx.get((league, season, d + timedelta(days=day_off)), [])
                # exact FT score is the primary guard against wrong fixtures
                cands = [c for c in cands if c[1] == hs and c[2] == as_]
                if not cands:
                    unmatched.append(f"{league} {code} {d} {row['HomeTeam']} {hs}-{as_} {row['AwayTeam']}")
                    rej += 1
                    continue
                want_h = ALIASES.get(canon(row["HomeTeam"]), canon(row["HomeTeam"]))
                want_a = ALIASES.get(canon(row["AwayTeam"]), canon(row["AwayTeam"]))
                if len(cands) == 1:
                    exact = cands  # league + date + exact score is unique
                else:
                    exact = [c for c in cands if canon(c[3]) == want_h and canon(c[4]) == want_a]
                    if not exact:
                        exact = [c for c in cands
                                 if difflib.SequenceMatcher(None, canon(c[3]), want_h).ratio() > 0.7
                                 and difflib.SequenceMatcher(None, canon(c[4]), want_a).ratio() > 0.7]
                if len(exact) != 1:
                    rej += 1
                    unmatched.append(f"AMBIG {league} {code} {d} {row['HomeTeam']} {hs}-{as_} {row['AwayTeam']}")
                    continue
                mid, _, _, _, _, sched = exact[0]
                with db.connect() as conn:
                    conn.execute(text("""
                        INSERT INTO odds_snapshots (snapshot_id, match_id, sportsbook, market_type,
                            home_odds, draw_odds, away_odds, captured_at)
                        VALUES (:s, :mid, 'Pinnacle', 'h2h', :h, :d, :a, :c)
                        ON CONFLICT (match_id, sportsbook, market_type, captured_at) DO NOTHING
                    """), {"s": uuid4(), "mid": mid, "h": ph, "d": pd_, "a": pa, "c": sched})
                    conn.commit()
                inserted += 1
                ok += 1
            matched += ok
            rejected += rej
            print(f"{league:16} {code}: {ok}/{len(df)} matched, {rej} rejected")

    with db.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM odds_snapshots")).scalar()
        covered = conn.execute(text("""
            SELECT COUNT(DISTINCT m.match_id) FROM matches m
            JOIN odds_snapshots o ON o.match_id = m.match_id
            WHERE m.status = 'FT'
        """)).scalar()
        ft_total = conn.execute(text("SELECT COUNT(*) FROM matches WHERE status='FT'")).scalar()
    print(f"\nInserted {inserted} snapshots ({rejected} rejected)")
    print(f"FT matches with odds: {covered}/{ft_total} (odds table total {total})")
    if unmatched:
        print(f"\nUnmatched/rejected ({len(unmatched)}):")
        for u in unmatched[:40]:
            print(f"  {u}")
        if len(unmatched) > 40:
            print(f"  ... and {len(unmatched) - 40} more")


if __name__ == "__main__":
    main()
