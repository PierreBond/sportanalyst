import os
from sqlalchemy import create_engine, text
db = create_engine(os.environ['DATABASE_URL_SYNC'])
with db.connect() as conn:
    r = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'teams' ORDER BY ordinal_position")).fetchall()
    for x in r:
        print(x)
