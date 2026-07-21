import json, os, re
from datetime import datetime, timezone
from difflib import get_close_matches
from uuid import uuid4
from sqlalchemy import create_engine, text

DB_URL = os.environ.get("DATABASE_URL_SYNC")

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
    """Build a map: normalized_team_name -> [team_id1, team_id2, ...]"""
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

# Manual aliases for clubs whose names differ completely between OP and DB
NAME_ALIASES = {
    "athletico pr": "paranaense",
    "athletico": "paranaense",
    "atletico mg": "ca mineiro",
    "atletico mineiro": "ca mineiro",
    "sao paulo": "sao paulo fc",
    "chapecoense sc": "chapecoense",
    "bragantino": "rb bragantino",
    "corinthians": "sc corinthians paulista",
    "flamengo": "cr flamengo",
    "fluminense": "fluminense fc",
    "vasco": "cr vasco da gama",
    "vasco da gama": "cr vasco da gama",
    "gremio": "gremio fbpa",
    "internacional": "sc internacional",
    "palmeiras": "se palmeiras",
    "coritiba": "coritiba fbc",
    "santos": "santos fc",
    "vitoria": "ec vitoria",
    "bahia": "ec bahia",
    "fortaleza": "fortaleza ec",
    "atletico go": "atletico goianiense",
    "goias": "goias",
    "ceara": "ceara",
    "cuiaba": "cuiaba",
    "mirassol": "mirassol fc",
    "juventude": "juventude",
    "criciuma": "criciuma",
    "avai": "avai",
    "america mineiro": "america mineiro",
    "operario pr": "operario",
    "ponte preta": "ponte preta",
    "botafogo rj": "botafogo fr",
    "botafogo": "botafogo fr",
    "cruzeiro": "cruzeiro ec",
    "remo": "clube do remo",
}

def match_team_ids(normalized_name, idx, cutoff=0.6):
    """Returns list of matching team_ids (exact + alias + contains + fuzzy)."""
    all_keys = list(idx.keys())
    matched_keys = set()
    # 0. Check alias
    alias = NAME_ALIASES.get(normalized_name)
    if alias and alias in idx:
        matched_keys.add(alias)
    # 1. Exact
    if normalized_name in idx:
        matched_keys.add(normalized_name)
    # 2. Contains (one is substring of the other)
    for k in all_keys:
        if normalized_name in k or k in normalized_name:
            matched_keys.add(k)
    # 3. Fuzzy
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

    total = 0
    now_dt = datetime.now(timezone.utc)

    for date_str in ["20260722", "20260725"]:
        fpath = f"odds_{date_str}.json"
        if not os.path.exists(fpath):
            print(f"{date_str}: no file")
            continue
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)

        inserted = 0
        unmatched = []
        dt_val = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

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
                    unmatched.append(f"no team match: {home}({hk}) -> {home_ids} vs {away}({ak}) -> {away_ids}")
                    continue

                found = False
                for hid in home_ids:
                    for aid in away_ids:
                        row = conn.execute(text(
                            "SELECT match_id FROM matches WHERE home_team_id = :hid AND away_team_id = :aid "
                            "AND DATE(scheduled_at) = DATE(:dt) LIMIT 1"
                        ), {"hid": hid, "aid": aid, "dt": dt_val}).fetchone()
                        if row:
                            q2 = text(
                                "INSERT INTO odds_snapshots (snapshot_id, match_id, sportsbook, market_type, "
                                "home_odds, draw_odds, away_odds, captured_at) "
                                "VALUES (:s,:m,'oddsportal-best','1x2',:h,:d,:a,:c) "
                                "ON CONFLICT (match_id, sportsbook, market_type, captured_at) DO NOTHING")
                            conn.execute(q2, {"s": uuid4(), "m": str(row[0]),
                                "h": mo["odds"][0], "d": mo["odds"][1], "a": mo["odds"][2], "c": now_dt})
                            inserted += 1
                            found = True
                            break
                    if found:
                        break
                if not found:
                    unmatched.append(f"no match row: {home} vs {away} on {date_str}")

            conn.commit()

        print(f"{date_str}: {inserted} inserted, {len(unmatched)} unmatched")
        if unmatched:
            print(f"  samples: {unmatched[:5]}")
        total += inserted

    print(f"\nTotal inserted: {total}")
    with db.connect() as conn:
        cnt = conn.execute(text("SELECT COUNT(*) FROM odds_snapshots")).scalar()
        print(f"odds_snapshots table: {cnt} rows")

if __name__ == "__main__":
    main()
