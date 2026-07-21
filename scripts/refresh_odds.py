"""Refresh odds from OddsPortal on a schedule."""
import json, os, re, subprocess, sys, time
from datetime import datetime, timezone
from difflib import get_close_matches
from uuid import uuid4
from sqlalchemy import create_engine, text

DB_URL = os.environ.get("DATABASE_URL_SYNC")
INTERVAL = int(os.environ.get("REFRESH_INTERVAL_MIN", "60")) * 60
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── aliases & normalize (same as insert_seriea.py) ──
NAME_ALIASES = {
    "athletico pr":"CA Paranaense","athletico":"CA Paranaense","atletico mg":"CA Mineiro",
    "atletico mineiro":"CA Mineiro","sao paulo":"São Paulo FC","chapecoense sc":"Chapecoense AF",
    "chapecoense":"Chapecoense AF","bragantino":"RB Bragantino","corinthians":"SC Corinthians Paulista",
    "flamengo rj":"CR Flamengo","flamengo":"CR Flamengo","fluminense":"Fluminense FC",
    "vasco":"CR Vasco da Gama","vasco da gama":"CR Vasco da Gama","gremio":"Grêmio FBPA",
    "internacional":"SC Internacional","palmeiras":"SE Palmeiras","coritiba":"Coritiba FBC",
    "santos":"Santos FC","vitoria":"EC Vitória","bahia":"EC Bahia","fortaleza":"Fortaleza EC",
    "mirassol":"Mirassol FC","botafogo rj":"Botafogo FR","botafogo":"Botafogo FR",
    "cruzeiro":"Cruzeiro EC","remo":"Clube do Remo",
}

def normalize(n):
    s = n.lower().strip().replace("-"," ").replace(".","").replace("  "," ")
    s = re.sub(r'\s+',' ', s)
    for p in ["fc ","sc ","ac ","ca ","cr ","se ","rb ","ec ","ae ","af ","ad","gr ","pr ","ag "]:
        if s.startswith(p): s = s[len(p):]
        if s.endswith(" "+p.strip()): s = s[:-(len(p.strip())+1)]
    s = re.sub(r'\s*\([a-z]{3}\)', '', s).strip()
    return re.sub(r'\s+',' ',s).strip()

def build_idx(conn):
    rows = conn.execute(text("SELECT team_id, LOWER(name), LOWER(COALESCE(short_name,'')) FROM teams")).fetchall()
    idx={}
    for r in rows:
        tid=str(r[0])
        for label in (r[1],r[2]):
            if label: idx.setdefault(normalize(label),set()).add(tid)
    return idx

def match_team_ids(nm, idx, cutoff=0.6):
    keys=list(idx.keys()); matched=set()
    a=NAME_ALIASES.get(nm)
    if a: n=normalize(a); matched.add(n) if n in idx else None
    if nm in idx: matched.add(nm)
    for k in keys:
        if nm in k or k in nm: matched.add(k)
    matched.update(get_close_matches(nm,keys,n=5,cutoff=cutoff))
    seen=set(); r=[]
    for k in matched:
        for t in idx[k]:
            if t not in seen: seen.add(t); r.append(t)
    return r

def scrape():
    print(f"[{datetime.now():%H:%M}] scraping OddsPortal...")
    r = subprocess.run(["agent-browser.cmd","open","https://www.oddsportal.com/football/brazil/serie-a-betano/"],
                       capture_output=True,text=True,timeout=90)
    if r.returncode != 0:
        print("  open failed:", r.stderr[:100])
        return
    r = subprocess.run(["agent-browser.cmd","wait","25000"], capture_output=True,text=True,timeout=60)
    r = subprocess.run(["agent-browser.cmd","eval","""JSON.stringify(Array.from(document.querySelectorAll('[class*="group"][class*="flex"]')).filter(row=>{const c=row.children;if(c.length<4)return false;const l=c[0];if(l.tagName!=='A')return false;return l.textContent.includes('\\u2013');}).map(row=>{const c=row.children;return{text:c[0].textContent.replace(/\\s+/g,' ').trim(),odds:[parseFloat(c[1].textContent),parseFloat(c[2].textContent),parseFloat(c[3].textContent)]};}))"""],
                       capture_output=True,text=True,timeout=60)
    if r.returncode != 0:
        print("  eval failed:", r.stderr[:100])
        return
    try:
        data = json.loads(r.stdout.strip())
    except json.JSONDecodeError:
        print("  JSON error")
        return
    if not data:
        print("  no matches")
        return

    db = create_engine(DB_URL)
    now_dt = datetime.now(timezone.utc)
    with db.connect() as conn:
        idx = build_idx(conn)
        dates = {r[0].isoformat()[:10]:r[0] for r in conn.execute(text(
            "SELECT DISTINCT DATE(scheduled_at) FROM matches WHERE (status IS NULL OR status='scheduled') "
            "AND scheduled_at>=NOW()-INTERVAL'1 day' AND scheduled_at<NOW()+INTERVAL'8 days' ORDER BY 1")).fetchall()}
        ins=0
        for mo in data:
            m=re.match(r'^(\d{1,2}:\d{2})(.*)\s*\u2013\s*(.*)$',mo["text"])
            if not m: continue
            home,away=m.group(2).strip(),m.group(3).strip()
            hids=match_team_ids(normalize(home),idx)
            aids=match_team_ids(normalize(away),idx)
            if not hids or not aids: continue
            found=False
            for hid in hids:
                for aid in aids:
                    for dt_str in dates:
                        row=conn.execute(text("SELECT match_id FROM matches WHERE home_team_id=:hid AND away_team_id=:aid AND DATE(scheduled_at)=DATE(:dt) LIMIT 1"),
                                        {"hid":hid,"aid":aid,"dt":dt_str}).fetchone()
                        if row:
                            conn.execute(text("INSERT INTO odds_snapshots(snapshot_id,match_id,sportsbook,market_type,home_odds,draw_odds,away_odds,captured_at) VALUES(:s,:m,'oddsportal-best','1x2',:h,:d,:a,:c) ON CONFLICT(match_id,sportsbook,market_type,captured_at)DO NOTHING"),
                                        {"s":uuid4(),"m":str(row[0]),"h":mo["odds"][0],"d":mo["odds"][1],"a":mo["odds"][2],"c":now_dt})
                            ins+=1; found=True; break
                    if found: break
                if found: break
        conn.commit()
        total=conn.execute(text("SELECT COUNT(*) FROM odds_snapshots")).scalar()
        print(f"  {ins} new, {total} total")

if __name__=="__main__":
    print("Odds refresher — Ctrl+C to stop")
    while True:
        scrape()
        print(f"  next run in {INTERVAL//60} min")
        time.sleep(INTERVAL)
