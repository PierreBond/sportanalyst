"""Batch predictions using trained XGBoost+Poisson model, writes to predictions table."""
import json, os, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4
import numpy as np
import joblib
from sqlalchemy import create_engine, text

DB_URL = os.environ.get("DATABASE_URL_SYNC")
MODEL_DIR = Path(__file__).resolve().parent.parent / "models"

def build_features(match_row, team_idx, league_idx, elos, db):
    mid, home, away, league, season, scheduled_at, home_tid, away_tid = match_row
    f = {k: 0.0 for k in [
        "home_team_encoded","away_team_encoded","league_encoded",
        "home_gf_avg_last3","home_ga_avg_last3","home_form_last3",
        "home_gf_avg_last5","home_ga_avg_last5","home_form_last5",
        "home_gf_avg_last10","home_ga_avg_last10","home_form_last10",
        "away_gf_avg_last3","away_ga_avg_last3","away_form_last3",
        "away_gf_avg_last5","away_ga_avg_last5","away_form_last5",
        "away_gf_avg_last10","away_ga_avg_last10","away_form_last10",
        "home_h_gf_avg_last5","home_h_ga_avg_last5","home_h_form_last5",
        "away_a_gf_avg_last5","away_a_ga_avg_last5","away_a_form_last5",
        "home_days_rest","away_days_rest","league_avg_total_goals",
        "h2h_home_gf_avg","h2h_away_gf_avg","h2h_home_wins","season",
        "home_elo","away_elo","elo_diff",
    ]}
    h_name = home if home in team_idx else (home.replace(" FC","").replace(" EC","").replace(" SC","").strip() if home else "")
    h_name = h_name if h_name in team_idx else home
    a_name = away if away in team_idx else (away.replace(" FC","").replace(" EC","").replace(" SC","").strip() if away else "")
    a_name = a_name if a_name in team_idx else away
    f["home_team_encoded"] = float(team_idx.get(h_name, 0))
    f["away_team_encoded"] = float(team_idx.get(a_name, 0))
    f["league_encoded"] = float(league_idx.get(league, 0))
    f["season"] = float(season or 2025)
    elo_h = elos.get(h_name, 1500)
    elo_a = elos.get(a_name, 1500)
    f["home_elo"] = elo_h + 100
    f["away_elo"] = elo_a
    f["elo_diff"] = f["home_elo"] - f["away_elo"]

    md = scheduled_at
    if not home_tid or not away_tid or not md:
        return f

    sql_roll = """
        WITH g AS (
            SELECT scheduled_at,
                CASE WHEN home_team_id=:tid THEN home_score ELSE away_score END AS scored,
                CASE WHEN home_team_id=:tid THEN away_score ELSE home_score END AS conceded,
                CASE WHEN (home_team_id=:tid AND home_score>away_score) OR (away_team_id=:tid AND away_score>home_score) THEN 3.0
                     WHEN home_score=away_score THEN 1.0 ELSE 0.0 END AS points
            FROM matches WHERE (home_team_id=:tid OR away_team_id=:tid) AND scheduled_at<:md AND status='FT' AND home_score IS NOT NULL
        ) SELECT AVG(scored), AVG(conceded), AVG(points) FROM (SELECT * FROM g ORDER BY scheduled_at DESC LIMIT :w) recent
    """
    sql_home = """
        WITH g AS (
            SELECT scheduled_at, home_score AS scored, away_score AS conceded,
                CASE WHEN home_score>away_score THEN 3.0 WHEN home_score=away_score THEN 1.0 ELSE 0.0 END AS points
            FROM matches WHERE home_team_id=:tid AND scheduled_at<:md AND status='FT' AND home_score IS NOT NULL
        ) SELECT AVG(scored), AVG(conceded), AVG(points) FROM (SELECT * FROM g ORDER BY scheduled_at DESC LIMIT :w) recent
    """
    sql_away = """
        WITH g AS (
            SELECT scheduled_at, away_score AS scored, home_score AS conceded,
                CASE WHEN away_score>home_score THEN 3.0 WHEN home_score=away_score THEN 1.0 ELSE 0.0 END AS points
            FROM matches WHERE away_team_id=:tid AND scheduled_at<:md AND status='FT' AND home_score IS NOT NULL
        ) SELECT AVG(scored), AVG(conceded), AVG(points) FROM (SELECT * FROM g ORDER BY scheduled_at DESC LIMIT :w) recent
    """
    sql_league_avg = "SELECT AVG(home_score+away_score) FROM matches WHERE league=:league AND status='FT' AND home_score IS NOT NULL"
    sql_h2h = """
        WITH h2h AS (
            SELECT home_score, away_score, home_team_id, away_team_id FROM matches
            WHERE ((home_team_id=:htid AND away_team_id=:atid) OR (home_team_id=:atid AND away_team_id=:htid))
            AND scheduled_at<:md AND status='FT' AND home_score IS NOT NULL ORDER BY scheduled_at DESC LIMIT 5
        ) SELECT AVG(CASE WHEN home_team_id=:htid2 THEN home_score ELSE away_score END) AS h_gf,
                 AVG(CASE WHEN away_team_id=:htid2 THEN away_score ELSE home_score END) AS h_conceded,
                 AVG(CASE WHEN (home_team_id=:htid2 AND home_score>away_score) OR (away_team_id=:htid2 AND away_score>home_score) THEN 1.0 WHEN home_score=away_score THEN 0.5 ELSE 0.0 END)
        FROM h2h
    """
    sql_last_match = """
        SELECT scheduled_at FROM matches WHERE (home_team_id=:tid OR away_team_id=:tid) AND scheduled_at<:md AND status='FT'
        ORDER BY scheduled_at DESC LIMIT 1
    """

    with db.connect() as conn2:
        for w in [3, 5, 10]:
            for side, tid in [("home", home_tid), ("away", away_tid)]:
                r = conn2.execute(text(sql_roll), {"tid": tid, "md": md, "w": w}).fetchone()
                if r and r[0] is not None:
                    f[f"{side}_gf_avg_last{w}"] = float(r[0])
                    f[f"{side}_ga_avg_last{w}"] = float(r[1])
                    f[f"{side}_form_last{w}"] = float(r[2])

        for side, tid in [("home", home_tid), ("away", away_tid)]:
            sql_s = sql_home if side == "home" else sql_away
            r = conn2.execute(text(sql_s), {"tid": tid, "md": md, "w": 5}).fetchone()
            if r and r[0] is not None:
                gf_key = f"{side}_h_gf_avg_last5" if side == "home" else f"{side}_a_gf_avg_last5"
                ga_key = f"{side}_h_ga_avg_last5" if side == "home" else f"{side}_a_ga_avg_last5"
                pt_key = f"{side}_h_form_last5" if side == "home" else f"{side}_a_form_last5"
                f[gf_key] = float(r[0])
                f[ga_key] = float(r[1])
                f[pt_key] = float(r[2])

            r2 = conn2.execute(text(sql_last_match), {"tid": tid, "md": md}).fetchone()
            if r2 and r2[0]:
                days = (md - r2[0]).total_seconds() / 86400
                f[f"{side}_days_rest"] = max(1, min(30, days))

        lr = conn2.execute(text(sql_league_avg), {"league": league}).fetchone()
        if lr and lr[0]:
            f["league_avg_total_goals"] = float(lr[0])

        hr = conn2.execute(text(sql_h2h), {"htid": home_tid, "atid": away_tid, "md": md, "htid2": home_tid}).fetchone()
        if hr and hr[0] is not None:
            f["h2h_home_gf_avg"] = float(hr[0])
            f["h2h_away_gf_avg"] = float(hr[1])
            f["h2h_home_wins"] = float(hr[2])
        else:
            f["h2h_home_wins"] = 0.5

    return f

def main():
    db = create_engine(DB_URL)
    meta = json.load(open(MODEL_DIR / "predictor_metadata.json"))
    model = joblib.load(MODEL_DIR / "predictor.joblib")
    fnames = meta["feature_names"]
    team_idx = {n: i for i, n in enumerate(meta["team_classes"])}
    league_idx = {n: i for i, n in enumerate(meta["league_classes"])}
    elos = meta["team_elos"]

    with db.connect() as conn:
        upcoming = conn.execute(text("""
            SELECT m.match_id::text, ht.name, at.name, m.league, m.season, m.scheduled_at,
                   m.home_team_id::text, m.away_team_id::text
            FROM matches m JOIN teams ht ON m.home_team_id=ht.team_id
            JOIN teams at ON m.away_team_id=at.team_id
            WHERE (m.status IS NULL OR m.status='scheduled')
            AND m.scheduled_at >= NOW() - INTERVAL '1 day'
            AND m.scheduled_at < NOW() + INTERVAL '8 days'
        """)).fetchall()

    now_dt = datetime.now(timezone.utc)
    ins = 0
    for u in upcoming:
        features = build_features(u, team_idx, league_idx, elos, db)
        feat_df = __import__("pandas").DataFrame([{k: features.get(k, 0.0) for k in fnames}])
        if hasattr(model, "predict_proba"):
            raw = model.predict_proba(feat_df)
            probs = raw[0]
        else:
            import xgboost as xgb
            probs = model.predict(xgb.DMatrix(feat_df, feature_names=fnames))

        mid = u[0]
        with db.connect() as conn:
            conn.execute(text("""
                INSERT INTO predictions (prediction_id, match_id, model_name, model_version,
                    predicted_at, home_win_prob, draw_prob, away_win_prob, is_live, created_at)
                VALUES (:pid,:mid,'ensemble_xgb_poisson','2.0',:now,:h,:d,:a,false,:now)
                ON CONFLICT DO NOTHING
            """), {"pid": uuid4(), "mid": mid, "now": now_dt,
                   "h": round(float(probs[0]), 4), "d": round(float(probs[1]), 4),
                   "a": round(float(probs[2]), 4)})
            ins += 1
            conn.commit()

    with db.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM predictions")).scalar()
    print(f"{ins} predictions inserted, {total} total")

if __name__ == "__main__":
    main()
