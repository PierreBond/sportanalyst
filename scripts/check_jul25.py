import os
from sqlalchemy import create_engine, text
db = create_engine(os.environ['DATABASE_URL_SYNC'])
with db.connect() as conn:
    rows = conn.execute(text("SELECT m.match_id, m.scheduled_at, ht.name, at.name FROM matches m JOIN teams ht ON m.home_team_id = ht.team_id JOIN teams at ON m.away_team_id = at.team_id WHERE m.scheduled_at::date = '2026-07-25' AND (m.status IS NULL OR m.status = 'scheduled') ORDER BY m.scheduled_at")).fetchall()
    for r in rows:
        print(f'{r[1].strftime("%m/%d %H:%M")} {r[2]} vs {r[3]}')
