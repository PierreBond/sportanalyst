"""Generate predictions from Elo ratings and insert into DB."""
import os
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import create_engine, text

DB_URL = os.environ.get("DATABASE_URL_SYNC")
K = 32
HOME_ADV = 100

def expected(rating_a, rating_b):
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))

def update_elo(ratings, home_id, away_id, home_score, away_score):
    r_h = ratings.get(home_id, 1500)
    r_a = ratings.get(away_id, 1500)
    e_h = expected(r_h + HOME_ADV, r_a)
    e_a = expected(r_a, r_h - HOME_ADV)
    if home_score > away_score:
        s_h, s_a = 1.0, 0.0
    elif home_score == away_score:
        s_h, s_a = 0.5, 0.5
    else:
        s_h, s_a = 0.0, 1.0
    ratings[home_id] = r_h + K * (s_h - e_h)
    ratings[away_id] = r_a + K * (s_a - e_a)

def main():
    db = create_engine(DB_URL)
    with db.connect() as conn:
        results = conn.execute(text(
            "SELECT m.home_team_id::text, m.away_team_id::text, m.home_score, m.away_score "
            "FROM matches m WHERE m.home_score IS NOT NULL ORDER BY m.scheduled_at ASC"
        )).fetchall()

    ratings = {}
    for r in results:
        update_elo(ratings, r[0], r[1], r[2], r[3])

    print(f"Rated {len(ratings)} teams")

    with db.connect() as conn:
        upcoming = conn.execute(text(
            "SELECT m.match_id::text, m.home_team_id::text, m.away_team_id::text, "
            "ht.name AS home, at.name AS away "
            "FROM matches m JOIN teams ht ON m.home_team_id = ht.team_id "
            "JOIN teams at ON m.away_team_id = at.team_id "
            "WHERE (m.status IS NULL OR m.status='scheduled') "
            "AND m.scheduled_at >= NOW() - INTERVAL '1 day' "
            "AND m.scheduled_at < NOW() + INTERVAL '8 days'"
        )).fetchall()

        now_dt = datetime.now(timezone.utc)
        ins = 0
        for u in upcoming:
            mid, hid, aid = u[0], u[1], u[2]
            r_h = ratings.get(hid, 1500)
            r_a = ratings.get(aid, 1500)
            e_h = expected(r_h + HOME_ADV, r_a)
            e_a = expected(r_a, r_h - HOME_ADV)
            e_d = max(0.0, 1.0 - e_h - e_a)
            # Normalize to sum to 1
            total = e_h + e_d + e_a
            p_h, p_d, p_a = e_h/total, e_d/total, e_a/total

            conn.execute(text(
                "INSERT INTO predictions (prediction_id, match_id, model_name, model_version, "
                "predicted_at, home_win_prob, draw_prob, away_win_prob, is_live, created_at) "
                "VALUES (:pid,:mid,'elo-rating','1.0',:now,:h,:d,:a,false,:now) "
                "ON CONFLICT DO NOTHING"
            ), {"pid": uuid4(), "mid": mid, "now": now_dt,
                "h": round(p_h, 4), "d": round(p_d, 4), "a": round(p_a, 4)})
            ins += 1

        conn.commit()
        total = conn.execute(text("SELECT COUNT(*) FROM predictions")).scalar()
        print(f"{ins} predictions inserted, {total} total")

if __name__ == "__main__":
    main()
