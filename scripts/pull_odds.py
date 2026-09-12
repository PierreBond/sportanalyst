"""Pull current odds from the-odds-api for upcoming matches and upsert into odds_snapshots."""
import json, os, re, sys
from datetime import datetime, timezone
from uuid import uuid4
from difflib import get_close_matches
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

def build_team_index(conn):
    rows = conn.execute(text("SELECT team_id, name, LOWER(COALESCE(short_name,'')) FROM teams")).fetchall()
    idx = {}
    for r in rows:
        tid = str(r[0])
        for label in (r[1], r[2]):
            if label:
                n = _remove_accents(label).lower().strip()
                idx.setdefault(n, set()).add(tid)
    return idx

NAME_ALIASES = {
    "atletico mineiro":"CA Mineiro","bragantino-sp":"RB Bragantino","bragantino":"RB Bragantino",
    "botafogo":"Botafogo FR","gremio":"Grêmio FBPA","chapecoense":"Chapecoense AF",
    "vasco da gama":"CR Vasco da Gama","sao paulo":"São Paulo FC","santos":"Santos FC",
    "internacional":"SC Internacional","flamengo":"CR Flamengo","mirassol":"Mirassol FC",
    "remo":"Clube do Remo","fluminense":"Fluminense FC","bahia":"EC Bahia",
    "vitoria":"EC Vitória","palmeiras":"SE Palmeiras","corinthians":"SC Corinthians Paulista",
    "atletico paranaense":"CA Paranaense","coritiba":"Coritiba FBC","cruzeiro":"Cruzeiro EC",
}

def match_team_ids(raw_name, idx, cutoff=0.6):
    n = _remove_accents(raw_name).lower().strip()
    alias = NAME_ALIASES.get(n)
    matched = set()
    if alias:
        ak = _remove_accents(alias).lower().strip()
        if ak in idx:
            matched.add(ak)
    if n in idx:
        matched.add(n)
    keys = list(idx.keys())
    for k in keys:
        if n in k or k in n:
            matched.add(k)
    matched.update(get_close_matches(n, keys, n=3, cutoff=cutoff))
    seen = set(); r = []
    for k in matched:
        for t in idx.get(k, set()):
            if t not in seen:
                seen.add(t); r.append(t)
    return r

def main():
    if not ODDS_API_KEY:
        print("ODDS_API_KEY not set"); sys.exit(1)
    db = create_engine(DB_URL)

    # Get upcoming match dates per league
    with db.connect() as conn:
        idx = build_team_index(conn)
        upcoming = conn.execute(text("""
            SELECT m.match_id::text, ht.name, at.name, m.league, DATE(m.scheduled_at)
            FROM matches m JOIN teams ht ON m.home_team_id=ht.team_id
            JOIN teams at ON m.away_team_id=at.team_id
            WHERE (m.status IS NULL OR m.status='scheduled')
            AND m.scheduled_at >= NOW() - INTERVAL '1 day'
            AND m.scheduled_at < NOW() + INTERVAL '8 days'
        """)).fetchall()

    match_map = {}  # (league, date) -> [(match_id, home_name, away_name)]
    for u in upcoming:
        key = (u[3], str(u[4]))
        match_map.setdefault(key, []).append((u[0], u[1], u[2]))

    now_dt = datetime.now(timezone.utc)
    inserted = 0
    remaining = 500
    errors = 0

    for (league, date_str), matches in match_map.items():
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

        def norm(n):
            return _remove_accents(n).lower().strip()
        def teams_match(db_h, db_a, api_h, api_a):
            dh, da = norm(db_h), norm(db_a)
            ah, aa = norm(api_h), norm(api_a)
            for hh, aa_ in [(dh, da), (da, dh)]:
                if (hh == ah or hh == NAME_ALIASES.get(ah, "")) and \
                   (aa_ == aa or aa_ == NAME_ALIASES.get(aa, "")):
                    return True
                if (hh in ah or ah in hh) and (aa_ in aa or aa in aa_):
                    return True
            return False

        api_matches = r.json()
        for mid, home_name, away_name in matches:
            best_h, best_d, best_a = None, None, None
            for am in api_matches:
                if not teams_match(home_name, away_name, am.get("home_team",""), am.get("away_team","")):
                    continue
                for bm in am.get("bookmakers", []):
                    for mk in bm.get("markets", []):
                        if mk.get("key") == "h2h":
                            outcomes = {o["name"]: o["price"] for o in mk["outcomes"]}
                            h_odd = outcomes.get(am.get("home_team"))
                            d_odd = outcomes.get("Draw")
                            a_odd = outcomes.get(am.get("away_team"))
                            if h_odd and d_odd and a_odd:
                                if best_h is None or h_odd < best_h:
                                    best_h, best_d, best_a = h_odd, d_odd, a_odd

            if best_h:
                with db.connect() as conn:
                    conn.execute(text("""
                        INSERT INTO odds_snapshots (snapshot_id, match_id, sportsbook, market_type,
                            home_odds, draw_odds, away_odds, captured_at)
                        VALUES (:s, :mid, 'the-odds-api', 'h2h', :h, :d, :a, :c)
                        ON CONFLICT (match_id, sportsbook, market_type, captured_at) DO NOTHING
                    """), {"s": uuid4(), "mid": mid, "h": best_h, "d": best_d, "a": best_a, "c": now_dt})
                    conn.commit()
                inserted += 1

        if remaining <= 0:
            break

    print(f"Inserted {inserted} odds snapshots, {remaining} requests remaining, {errors} errors")

if __name__ == "__main__":
    main()
