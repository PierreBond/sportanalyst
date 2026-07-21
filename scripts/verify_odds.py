import os
from sqlalchemy import create_engine, text
from datetime import datetime, timezone

db = create_engine(os.environ['DATABASE_URL_SYNC'])
with db.connect() as conn:
    rows = conn.execute(text("""
        SELECT m.scheduled_at::date as d, ht.name as h, at.name as a, 
               os.home_odds, os.draw_odds, os.away_odds, os.captured_at
        FROM odds_snapshots os
        JOIN matches m ON os.match_id = m.match_id
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        ORDER BY m.scheduled_at, ht.name
    """)).fetchall()
    print(f"Total rows: {len(rows)}")
    for r in rows:
        print(f'{r[0]} {r[1]:35s} vs {r[2]:35s} | {r[3]:>6.2f} {r[4]:>6.2f} {r[5]:>6.2f} | {r[6].strftime("%H:%M")}')
