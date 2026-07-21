"""Fast odds scraper — extracts 1x2 from OddsPortal listing page."""
import asyncio, os, re, sys
from datetime import datetime, timezone
from difflib import get_close_matches
from uuid import uuid4

from playwright.async_api import async_playwright
from sqlalchemy import create_engine, text

DB_URL = os.environ.get("DATABASE_URL_SYNC", "postgresql://user:pass@localhost:5432/sportspred")

STEALTH = """Object.defineProperty(navigator,"webdriver",{get:()=>undefined});"""

def normalize(n: str) -> str:
    s = n.lower().strip().replace("-"," ").replace(".","")
    s = re.sub(r'\s+',' ',s)
    for p in ["fc ","sc ","ac ","ca ","cr ","se ","rb ","ec ","ae ","gr ","af ","fr","pr"]:
        if s.startswith(p): s = s[len(p):]
        if s.endswith(" "+p.strip()): s = s[:-(len(p.strip())+1)]
    return s.strip()

def build_idx(conn):
    rows = conn.execute(text("SELECT team_id, LOWER(name), LOWER(COALESCE(short_name,'')) FROM teams")).fetchall()
    idx = {}
    for r in rows:
        for label in (r[1], r[2]):
            if label: idx[normalize(label)] = (r[0], r[1])
    return idx

async def main():
    headless = "--headed" not in sys.argv
    db = create_engine(DB_URL)

    with db.connect() as conn:
        dates = conn.execute(text("""
            SELECT DISTINCT DATE(scheduled_at) FROM matches
            WHERE (status IS NULL OR status = 'scheduled')
            AND scheduled_at >= NOW() AND scheduled_at < NOW() + INTERVAL '7 days'
            ORDER BY 1
        """)).fetchall()
        date_strs = [r[0].strftime("%Y%m%d") for r in dates]
        print(f"Dates: {date_strs}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless,
            args=["--disable-blink-features=AutomationControlled"])
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080})
        await ctx.add_init_script(STEALTH)

        for date_str in date_strs:
            url = f"https://www.oddsportal.com/matches/football/{date_str}/"
            page = await ctx.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                # Wait for Vue to render match content
                await page.wait_for_timeout(20000)
                # Try waiting for any element containing odds-like text
                try:
                    await page.wait_for_selector("text=1.", timeout=5000)
                except:
                    pass
                await page.wait_for_timeout(3000)
                page_html = await page.content()
                page_text = await page.inner_text("body")
                with open(f"debug_{date_str}.html", "w", encoding="utf-8") as f:
                    f.write(page_html)
            except Exception as e:
                print(f"  Error: {e}")
                page_text = ""

            if not page_text:
                print(f"  {date_str}: no content (page empty or blocked)")
                await page.close()
                continue

            lines = [l.strip() for l in page_text.split("\n") if l.strip()]
            print(f"  Total lines: {len(lines)}, has odds: {any('1.' in l for l in lines)}")
            # Try a JS evaluation to find match data
            matches_js = await page.evaluate("""
                () => {
                    const els = document.querySelectorAll('a, button, span, div');
                    return Array.from(els).filter(e => /\\d{1,2}:\\d{2}/.test(e.textContent)).slice(0,5).map(e => e.textContent.trim());
                }
            """)
            print(f"  JS text matches: {matches_js}")
            await page.close()

            if not page_text:
                print(f"  {date_str}: no content (page empty or blocked)")
                continue
            matches = []
            for i, line in enumerate(lines):
                # Match lines like "23:30 Coritiba Coritiba – Palmeiras Palmeiras"
                m = re.match(r'^(\d{1,2}:\d{2})\s+(.+?)\s+[–\-]\s+(.+)$', line)
                if m:
                    time_part = m.group(1)
                    home_raw = m.group(2).strip()
                    away_raw = m.group(3).strip()
                    # Oddsportal duplicates team names: "Coritiba Coritiba" -> "Coritiba"
                    home = re.sub(r'\s+', ' ', home_raw).strip()
                    away = re.sub(r'\s+', ' ', away_raw).strip()
                    # Find odds - they're the next non-empty lines with decimal format
                    odds = []
                    j = i + 1
                    while j < len(lines) and len(odds) < 3:
                        ol = re.match(r'^(\d+\.\d{2})$', lines[j])
                        if ol:
                            odds.append(float(ol.group(1)))
                        j += 1
                    if len(odds) == 3:
                        matches.append({"home": home, "away": away, "odds": odds, "time": time_part})

            print(f"  {date_str}: {len(matches)} matches parsed")

            with db.connect() as conn:
                idx = build_idx(conn)
                unmatched, inserted = 0, 0
                now_dt = datetime.now(timezone.utc)
                for m in matches:
                    home_key = normalize(m["home"])
                    away_key = normalize(m["away"])
                    home = get_close_matches(home_key, idx.keys(), n=1, cutoff=0.6)
                    away = get_close_matches(away_key, idx.keys(), n=1, cutoff=0.6)
                    if not home or not away:
                        unmatched += 1
                        continue
                    home_id = idx[home[0]][0]
                    away_id = idx[away[0]][0]
                    row = conn.execute(text("""
                        SELECT match_id FROM matches
                        WHERE home_team_id = :hid AND away_team_id = :aid
                        AND scheduled_at::date = :dt::date LIMIT 1
                    """), {"hid": str(home_id), "aid": str(away_id),
                           "dt": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"}).fetchone()
                    if not row:
                        unmatched += 1
                        continue
                    conn.execute(text("""
                        INSERT INTO odds_snapshots
                        (snapshot_id, match_id, sportsbook, market_type, home_odds, draw_odds, away_odds, captured_at)
                        VALUES (:s,:m,'oddsportal-best','1x2',:h,:d,:a,:c)
                        ON CONFLICT (match_id, sportsbook, market_type, captured_at) DO NOTHING
                    """), {"s": uuid4(), "m": str(row[0]),
                           "h": m["odds"][0], "d": m["odds"][1], "a": m["odds"][2], "c": now_dt})
                    inserted += 1
                conn.commit()
                print(f"    Inserted: {inserted}, Unmatched: {unmatched}")

        await browser.close()

    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
