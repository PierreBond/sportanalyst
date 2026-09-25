"""Pull current odds from the-odds-api for upcoming matches and upsert into odds_snapshots."""
import os
import re
import sys
from datetime import datetime, timezone
from uuid import uuid4
import httpx
from sqlalchemy import create_engine, text

DB_URL = os.environ.get("DATABASE_URL_SYNC")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
LEAGUE_SPORT_MAP = {
    "brasileirao": "soccer_brazil_campeonato",
    "bundesliga": "soccer_germany_bundesliga",
    "eredivisie": "soccer_netherlands_eredivisie",
    "j1_league": "soccer_japan_j_league",
    "la_liga": "soccer_spain_la_liga",
    "ligue_1": "soccer_france_ligue_one",
    "mls": "soccer_usa_mls",
    "premier_league": "soccer_epl",
    "serie_a": "soccer_italy_serie_a",
}

def _remove_accents(t):
    import unicodedata
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode("ascii")

def canon(n):
    """Canonical team name for cross-source matching.

    Strips accents/punctuation/digits and club prefixes so that
    "FC Bayern München" == "Bayern Munich", "Brighton & Hove Albion FC"
    == "Brighton and Hove Albion", "Bayer 04 Leverkusen" == "Bayer Leverkusen".
    """
    n = _remove_accents(n).lower().strip()
    n = n.replace("&", " and ")
    n = re.sub(r"[^a-z0-9\s]", " ", n)
    n = re.sub(r"\b\d+\b", " ", n)
    n = re.sub(r"\b(fc|sc|cf|ac|afc|ca|rb|ssc|ss|rc|rcd|sv|vfl|vfb|tsg|us|club|de|del)\b", " ", n)
    n = n.replace("munchen", "munich")
    n = n.replace("internazionale", "inter")
    n = n.replace("rennais", "rennes")
    return re.sub(r"\s+", " ", n).strip()

def main():
    if not ODDS_API_KEY:
        print("ODDS_API_KEY not set")
        sys.exit(1)
    db = create_engine(DB_URL)

    # Get upcoming match dates per league
    with db.connect() as conn:
        upcoming = conn.execute(text("""
            SELECT m.match_id::text, ht.name, at.name, m.league, m.scheduled_at
            FROM matches m JOIN teams ht ON m.home_team_id=ht.team_id
            JOIN teams at ON m.away_team_id=at.team_id
            WHERE (m.status IS NULL OR m.status='scheduled')
            AND m.scheduled_at >= NOW() - INTERVAL '1 day'
            AND m.scheduled_at < NOW() + INTERVAL '34 days'
        """)).fetchall()

    match_map = {}  # league -> [(match_id, home_name, away_name, scheduled_at)]
    for u in upcoming:
        match_map.setdefault(u[3], []).append((u[0], u[1], u[2], u[4]))

    now_dt = datetime.now(timezone.utc)
    inserted = 0
    remaining = 500
    errors = 0

    for league, matches in match_map.items():
        sport_key = LEAGUE_SPORT_MAP.get(league)
        if not sport_key:
            continue

        r = httpx.get(
            f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=h2h",
            timeout=15,
        )
        remaining = int(r.headers.get("x-requests-remaining", 0))
        if r.status_code != 200:
            errors += 1
            continue

        def teams_match(db_h, db_a, api_h, api_a):
            dh, da, ah, aa = canon(db_h), canon(db_a), canon(api_h), canon(api_a)
            if not (dh and da and ah and aa):
                return False
            for hh, aa_ in [(dh, da), (da, dh)]:
                if (hh in ah or ah in hh) and (aa_ in aa or aa in aa_):
                    return True
            return False

        api_matches = r.json()
        unmatched = []
        for mid, home_name, away_name, sched in matches:
            best_h, best_d, best_a, best_sb = None, None, None, None
            for am in api_matches:
                if not teams_match(home_name, away_name, am.get("home_team",""), am.get("away_team","")):
                    continue
                # date sanity: DB often stores date-only placeholders (00:00)
                # that disagree with real kickoff times by a few days; same
                # pairing can't recur within a week in league play, while the
                # wrong-fixture case (swap + substring match) was 11 days off.
                am_date = am.get("commence_time", "")[:10]
                if not am_date or abs((datetime.fromisoformat(am_date).date() - sched.date()).days) > 7:
                    continue
                # one sane book per event (Pinnacle first). min-per-leg across
                # books picked up Betfair junk rows (1.1/1.13) and produced
                # odds no single book offers.
                for bm in sorted(am.get("bookmakers", []),
                                 key=lambda b: b.get("title") != "Pinnacle"):
                    for mk in bm.get("markets", []):
                        if mk.get("key") != "h2h":
                            continue
                        outcomes = {o["name"]: o["price"] for o in mk["outcomes"]}
                        h_odd = outcomes.get(am.get("home_team"))
                        d_odd = outcomes.get("Draw")
                        a_odd = outcomes.get(am.get("away_team"))
                        if not (h_odd and d_odd and a_odd and h_odd > 1
                                and d_odd > 1 and a_odd > 1):
                            continue
                        # 3-way implied sum must be a realistic vig (0.95-1.15);
                        # rejects exchange placeholders like 1000/1000/1000
                        s = 1.0 / h_odd + 1.0 / d_odd + 1.0 / a_odd
                        if 0.95 <= s <= 1.15:
                            best_h, best_d, best_a = h_odd, d_odd, a_odd
                            best_sb = bm.get("title", "unknown")
                            break
                    if best_h is not None:
                        break
                if best_h is not None:
                    break

            if best_h:
                with db.connect() as conn:
                    conn.execute(text("""
                        INSERT INTO odds_snapshots (snapshot_id, match_id, sportsbook, market_type,
                            home_odds, draw_odds, away_odds, captured_at)
                        VALUES (:s, :mid, :sb, 'h2h', :h, :d, :a, :c)
                        ON CONFLICT (match_id, sportsbook, market_type, captured_at) DO NOTHING
                    """), {"s": uuid4(), "mid": mid, "sb": best_sb, "h": best_h,
                           "d": best_d, "a": best_a, "c": now_dt})
                    conn.commit()
                inserted += 1
            else:
                unmatched.append(f"{home_name} vs {away_name}")

        got = len(matches) - len(unmatched)
        print(f"  [{league}] {got}/{len(matches)} matches got odds")
        if unmatched:
            print(f"    unmatched: {'; '.join(unmatched)}")

        if remaining <= 0:
            break

    print(f"Inserted {inserted} odds snapshots, {remaining} requests remaining, {errors} errors")

if __name__ == "__main__":
    main()
