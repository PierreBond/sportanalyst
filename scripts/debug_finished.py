import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='sportspred', user='user', password='pass')
cur = conn.cursor()

cur.execute("""
    SELECT m.match_id::text, ht.name, at.name, m.league, m.scheduled_at
    FROM matches m
    JOIN teams ht ON ht.team_id = m.home_team_id
    JOIN teams at ON at.team_id = m.away_team_id
    WHERE m.status = 'finished' AND m.home_score IS NULL
    ORDER BY m.scheduled_at
    LIMIT 30
""")
print("=== Sample finished matches without scores ===")
for row in cur.fetchall():
    print(f"  {row[0][:8]}... {row[1]} vs {row[2]} [{row[3]}] {row[4]}")

cur.execute("""
    SELECT m.league, count(*)
    FROM matches m
    WHERE m.status = 'finished' AND m.home_score IS NULL
    GROUP BY m.league
    ORDER BY count(*) DESC
""")
print("\n=== By league ===")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

cur.execute("""
    SELECT min(scheduled_at), max(scheduled_at)
    FROM matches
    WHERE status = 'finished' AND home_score IS NULL
""")
row = cur.fetchone()
print(f"\n=== Date range ===")
print(f"  {row[0]} to {row[1]}")

conn.close()
