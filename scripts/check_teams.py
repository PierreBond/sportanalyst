import os
from sqlalchemy import create_engine, text
db = create_engine(os.environ['DATABASE_URL_SYNC'])
with db.connect() as conn:
    r = conn.execute(text("SELECT name, short_name FROM teams ORDER BY name")).fetchall()
    for x in r:
        print(f'{x[0]} | {x[1]}')
