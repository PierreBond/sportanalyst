import os
from sqlalchemy import create_engine, text
from collections import Counter
db = create_engine(os.environ['DATABASE_URL_SYNC'])
with db.connect() as conn:
    # Count how many times each team appears in matches
    home = conn.execute(text("SELECT ht.name, COUNT(*) FROM matches m JOIN teams ht ON m.home_team_id = ht.team_id WHERE m.scheduled_at >= NOW() - INTERVAL '30 days' GROUP BY ht.name ORDER BY COUNT(*) DESC LIMIT 20")).fetchall()
    print("Home teams in recent matches:")
    for r in home:
        print(f"  {r[0]}: {r[1]}")
