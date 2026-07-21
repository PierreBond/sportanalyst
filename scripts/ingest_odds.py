import json, os, re, subprocess, sys, tempfile
from datetime import datetime, timezone
from difflib import get_close_matches
from uuid import uuid4

from sqlalchemy import create_engine, text

DB_URL = os.environ.get("DATABASE_URL_SYNC", "postgresql://user:pass@localhost:5432/sportspred")

AGENT_BROWSER = "agent-browser.cmd"

EXTRACT_JS = """
JSON.stringify(Array.from(document.querySelectorAll('div.group.flex')).map(row => {
  const children = row.children;
  if (children.length < 4) return null;
  const link = children[0];
  if (link.tagName !== 'A') return null;
  const text = link.textContent.replace(/\\s+/g,' ').trim();
  if (!text.includes('\\u2013')) return null;
  const odds = [];
  for (let i = 1; i <= 3; i++) {
    const t = children[i].textContent.replace(/\\s+/g,' ').trim();
    const v = parseFloat(t);
    if (!isNaN(v)) odds.push(v);
  }
  return odds.length === 3 ? {text, odds} : null;
}).filter(Boolean))
"""

def normalize(n):
    s = n.lower().strip().replace("-"," ").replace(".","").replace("  "," ")
    s = re.sub(r'\s+',' ', s)
    for prefix in ["fc ","sc ","ac ","ca ","cr ","se ","rb ","ec ","ae ","gr ","af ","fr","pr "]:
        if s.startswith(prefix): s = s[len(prefix):]
        if s.endswith(" "+prefix.strip()): s = s[:-(len(prefix.strip())+1)]
    # Remove country codes like (Bra), (Eng) etc.
    s = re.sub(r'\s*\([a-z]{3}\)', '', s).strip()
    return s

def build_idx(conn):
    rows = conn.execute(text("SELECT team_id, LOWER(name), LOWER(COALESCE(short_name,'')), LOWER(COALESCE(abbreviation,'')) FROM teams")).fetchall()
    idx = {}
    for r in rows:
        for label in (r[1], r[2], r[3]):
            if label: idx[normalize(label)] = (str(r[0]), r[1])
    return idx

def extract_oddsportal(date_str):
    url = f"https://www.oddsportal.com/matches/football/{date_str}/"
    cmds = [
        [AGENT_BROWSER, "open", url],
        [AGENT_BROWSER, "wait", "25000"],
        [AGENT_BROWSER, "eval", EXTRACT_JS],
    ]
    result = None
    for cmd in cmds:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            print(f"  agent-browser error: {r.stderr[:200]}")
            return []
        if cmd[1] == "eval":
            try:
                result = json.loads(r.stdout.strip())
            except json.JSONDecodeError:
                print(f"  JSON parse error: {r.stdout[:200]}")
                return []
    return result or []

def parse_match(text):
    m = re.match(r'^(\d{1,2}:\d{2})(.+?)\s*[–\-]\s*(.+)$', text)
    if not m:
        return None
    time_part = m.group(1)
    home = m.group(2).strip()
    away = m.group(3).strip()
    return {"time": time_part, "home": home, "away": away}

def match_team(normalized_name, idx, cutoff=0.6):
    matches = get_close_matches(normalized_name, idx.keys(), n=1, cutoff=cutoff)
    if matches:
        return idx[matches[0]][0]
    return None

def main():
    db = create_engine(DB_URL)

    with db.connect() as conn:
        dates = conn.execute(text("""
            SELECT DISTINCT DATE(scheduled_at) FROM matches
            WHERE (status IS NULL OR status = 'scheduled')
            AND scheduled_at >= NOW() AND scheduled_at < NOW() + INTERVAL '7 days'
            ORDER BY 1
        """)).fetchall()
        date_strs = [r[0].strftime("%Y%m%d") for r in dates]
        print(f"DB dates: {date_strs}")

    total_inserted = 0
    for date_str in date_strs:
        print(f"\n=== {date_str} ===")
        matches_odds = extract_oddsportal(date_str)
        if not matches_odds:
            print(f"  No matches found")
            continue
        print(f"  OP matches: {len(matches_odds)}")

        with db.connect() as conn:
            idx = build_idx(conn)
            inserted = 0
            unmatched_names = []
            now_dt = datetime.now(timezone.utc)

            for mo in matches_odds:
                parsed = parse_match(mo["text"])
                if not parsed:
                    continue

                home_key = normalize(parsed["home"])
                away_key = normalize(parsed["away"])
                home_id = match_team(home_key, idx)
                away_id = match_team(away_key, idx)

                if not home_id or not away_id:
                    unmatched_names.append(f"{parsed['home']}({home_key}) vs {parsed['away']}({away_key})")
                    continue

                row = conn.execute(text("""
                    SELECT match_id FROM matches
                    WHERE home_team_id = :hid AND away_team_id = :aid
                    AND scheduled_at::date = :dt::date LIMIT 1
                """), {"hid": home_id, "aid": away_id,
                       "dt": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"}).fetchone()
                if not row:
                    unmatched_names.append(f"{parsed['home']} vs {parsed['away']} (no match row)")
                    continue

                conn.execute(text("""
                    INSERT INTO odds_snapshots
                    (snapshot_id, match_id, sportsbook, market_type, home_odds, draw_odds, away_odds, captured_at)
                    VALUES (:s,:m,'oddsportal-best','1x2',:h,:d,:a,:c)
                    ON CONFLICT (match_id, sportsbook, market_type, captured_at) DO NOTHING
                """), {"s": uuid4(), "m": str(row[0]),
                       "h": mo["odds"][0], "d": mo["odds"][1], "a": mo["odds"][2], "c": now_dt})
                inserted += 1

            conn.commit()
            total_inserted += inserted
            print(f"  Inserted: {inserted}, Unmatched: {len(unmatched_names)}")
            if unmatched_names:
                print(f"  Sample unmatched: {unmatched_names[:5]}")

    print(f"\nTotal inserted: {total_inserted}")

if __name__ == "__main__":
    main()
