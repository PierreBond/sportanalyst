import json, os, re
from datetime import datetime, timezone, date, timedelta
from difflib import get_close_matches
from uuid import uuid4
from sqlalchemy import create_engine, text

DB_URL = os.environ.get("DATABASE_URL_SYNC")

# Aliases: OP name (normalized) -> DB name (raw, will be normalized in lookup)
NAME_ALIASES = {
    "athletico pr": "CA Paranaense",
    "athletico": "CA Paranaense",
    "atletico mg": "CA Mineiro",
    "atletico mineiro": "CA Mineiro",
    "sao paulo": "São Paulo FC",
    "chapecoense sc": "Chapecoense AF",
    "chapecoense": "Chapecoense AF",
    "bragantino": "RB Bragantino",
    "corinthians": "SC Corinthians Paulista",
    "flamengo rj": "CR Flamengo",
    "flamengo": "CR Flamengo",
    "fluminense": "Fluminense FC",
    "vasco": "CR Vasco da Gama",
    "vasco da gama": "CR Vasco da Gama",
    "gremio": "Grêmio FBPA",
    "internacional": "SC Internacional",
    "palmeiras": "SE Palmeiras",
    "coritiba": "Coritiba FBC",
    "santos": "Santos FC",
    "vitoria": "EC Vitória",
    "bahia": "EC Bahia",
    "fortaleza": "Fortaleza EC",
    "mirassol": "Mirassol FC",
    "botafogo rj": "Botafogo FR",
    "botafogo": "Botafogo FR",
    "cruzeiro": "Cruzeiro EC",
    "remo": "Clube do Remo",
}

def normalize(n):
    s = n.lower().strip().replace("-"," ").replace(".","").replace("  "," ")
    s = re.sub(r'\s+',' ', s)
    for p in ["fc ","sc ","ac ","ca ","cr ","se ","rb ","ec ","ae ","af ","ad","gr ","pr ","ag "]:
        if s.startswith(p): s = s[len(p):]
        if s.endswith(" "+p.strip()): s = s[:-(len(p.strip())+1)]
    s = re.sub(r'\s*\([a-z]{3}\)', '', s).strip()
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

def build_match_map(conn):
    rows = conn.execute(text(
        "SELECT team_id, LOWER(name), LOWER(COALESCE(short_name,'')) FROM teams"
    )).fetchall()
    idx = {}
    for r in rows:
        tid = str(r[0])
        for label in (r[1], r[2]):
            if label:
                n = normalize(label)
                idx.setdefault(n, set()).add(tid)
    return idx

def match_team_ids(normalized_name, idx, cutoff=0.6):
    all_keys = list(idx.keys())
    matched_keys = set()
    # Alias: normalize target too
    alias = NAME_ALIASES.get(normalized_name)
    if alias:
        alias_n = normalize(alias)
        if alias_n in idx:
            matched_keys.add(alias_n)
    if normalized_name in idx:
        matched_keys.add(normalized_name)
    for k in all_keys:
        if normalized_name in k or k in normalized_name:
            matched_keys.add(k)
    fuzzy = get_close_matches(normalized_name, all_keys, n=5, cutoff=cutoff)
    matched_keys.update(fuzzy)
    seen = set()
    result = []
    for k in matched_keys:
        for tid in idx[k]:
            if tid not in seen:
                seen.add(tid)
                result.append(tid)
    return result

def main():
    db = create_engine(DB_URL)
    with db.connect() as conn:
        idx = build_match_map(conn)
        print(f"Indexed {len(idx)} normalized names")
        # Get all upcoming match dates
        date_rows = conn.execute(text(
            "SELECT DISTINCT DATE(scheduled_at) FROM matches "
            "WHERE (status IS NULL OR status = 'scheduled') "
            "AND scheduled_at >= NOW() - INTERVAL '1 day' "
            "AND scheduled_at < NOW() + INTERVAL '8 days' ORDER BY 1"
        )).fetchall()
        db_dates = {r[0].isoformat()[:10]: r[0] for r in date_rows}
        print(f"DB dates: {sorted(db_dates.keys())}")

    fpath = "odds_seriea.json"
    with open(fpath, encoding="utf-8") as f:
        data = json.load(f)

    total = 0
    now_dt = datetime.now(timezone.utc)
    unmatched = []

    with db.connect() as conn:
        for mo in data:
            m = re.match(r'^(\d{1,2}:\d{2})(.*)\s*\u2013\s*(.*)$', mo["text"])
            if not m:
                unmatched.append(f"parse fail: {mo['text']}")
                continue
            home, away = m.group(2).strip(), m.group(3).strip()
            hk, ak = normalize(home), normalize(away)
            home_ids = match_team_ids(hk, idx)
            away_ids = match_team_ids(ak, idx)
            if not home_ids or not away_ids:
                unmatched.append(f"no team: {home}({hk}) -> {home_ids} vs {away}({ak}) -> {away_ids}")
                continue

            found = False
            for hid in home_ids:
                for aid in away_ids:
                    for dt_str, dt_date in db_dates.items():
                        row = conn.execute(text(
                            "SELECT match_id FROM matches WHERE home_team_id = :hid AND away_team_id = :aid "
                            "AND DATE(scheduled_at) = DATE(:dt) LIMIT 1"
                        ), {"hid": hid, "aid": aid, "dt": dt_str}).fetchone()
                        if row:
                            q2 = text(
                                "INSERT INTO odds_snapshots (snapshot_id, match_id, sportsbook, market_type, "
                                "home_odds, draw_odds, away_odds, captured_at) "
                                "VALUES (:s,:m,'oddsportal-best','1x2',:h,:d,:a,:c) "
                                "ON CONFLICT (match_id, sportsbook, market_type, captured_at) DO NOTHING")
                            conn.execute(q2, {"s": uuid4(), "m": str(row[0]),
                                "h": mo["odds"][0], "d": mo["odds"][1], "a": mo["odds"][2], "c": now_dt})
                            total += 1
                            found = True
                            break
                    if found:
                        break
                if found:
                    break
            if not found:
                unmatched.append(f"no row: {home} vs {away}")

        conn.commit()

    print(f"Inserted: {total}, Unmatched: {len(unmatched)}")
    if unmatched:
        print(f"  samples: {unmatched[:10]}")

    with db.connect() as conn:
        cnt = conn.execute(text("SELECT COUNT(*) FROM odds_snapshots")).scalar()
        print(f"odds_snapshots table: {cnt} rows")

if __name__ == "__main__":
    main()
