"""Check which finished matches still lack scores, by league."""
import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='sportspred', user='user', password='pass')
cur = conn.cursor()

cur.execute("""
    SELECT m.league, count(*)
    FROM matches m
    WHERE m.status = 'finished' AND m.home_score IS NULL
    GROUP BY m.league
    ORDER BY count(*) DESC
""")
print("=== Still missing scores by league ===")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

conn.close()
