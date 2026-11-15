"""Fit the probability calibrator on historical training data.

Uses seasons[:-1] (everything except the most recent season) as calibration data,
matching the train/test split used by train_model.py. This avoids data leakage
from the test season.

Outputs models/calibrator.json which is auto-loaded at serving startup.
"""
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "libs"))

from services.model_serving.src.calibrator import ProbabilityCalibrator


def main():
    DB_URL = "postgresql://user:pass@localhost:5432/sportspred"
    engine = create_engine(DB_URL)

    print("Loading match data...")
    df = pd.read_sql("""
        SELECT m.match_id, m.league, m.season, m.round,
               m.scheduled_at, m.home_score, m.away_score,
               ht.name AS home_team, at.name AS away_team,
               m.home_team_id, m.away_team_id
        FROM matches m
        JOIN teams ht ON ht.team_id = m.home_team_id
        JOIN teams at ON at.team_id = m.away_team_id
        WHERE m.home_score IS NOT NULL AND m.away_score IS NOT NULL
          AND m.status = 'FT'
        ORDER BY m.scheduled_at
    """, engine)
    engine.dispose()

    print(f"Loaded {len(df)} matches")
    print(f"Seasons: {sorted(df['season'].unique())}")

    # Engineer features
    print("Engineering features (this may take a few minutes...)")
    df, _elo_df = engineer_features(df)

    # Split: train = all seasons except the last (2026 is test season)
    seasons = sorted(df["season"].unique())
    test_season = seasons[-1]
    train_mask = df["season"] != test_season
    print(f"Train seasons: {[s for s in seasons if s != test_season]}")
    print(f"Test season: {test_season}")
    print(f"Train matches: {train_mask.sum()}")

    df_train = df.loc[train_mask].reset_index(drop=True)

    # Load odds snapshots (same as train_model.py)
    engine2 = create_engine(DB_URL)
    odds_df = pd.read_sql("""
        SELECT DISTINCT ON (match_id) match_id::text, home_odds, draw_odds, away_odds
        FROM odds_snapshots ORDER BY match_id, captured_at DESC
    """, engine2)
    engine2.dispose()
    odds_df["match_id"] = odds_df["match_id"].astype(str)
    df_train["match_id"] = df_train["match_id"].astype(str)
    df_train = df_train.merge(odds_df, on="match_id", how="left")
    for c in ["home_odds", "draw_odds", "away_odds"]:
        df_train[c] = df_train[c].fillna(0.0).astype(float)
    inv = pd.DataFrame({
        "h": np.where(df_train["home_odds"] > 0, 1.0 / df_train["home_odds"], 0),
        "d": np.where(df_train["draw_odds"] > 0, 1.0 / df_train["draw_odds"], 0),
        "a": np.where(df_train["away_odds"] > 0, 1.0 / df_train["away_odds"], 0),
    })
    denom = inv.sum(axis=1)
    df_train["home_implied_prob"] = np.where(denom > 0, inv["h"] / denom, 0.0)
    df_train["draw_implied_prob"] = np.where(denom > 0, inv["d"] / denom, 0.0)
    df_train["away_implied_prob"] = np.where(denom > 0, inv["a"] / denom, 0.0)

    # Build feature matrix using the same FEATURES list as training
    le_team = __import__("sklearn.preprocessing", fromlist=["LabelEncoder"]).LabelEncoder()
    le_league = __import__("sklearn.preprocessing", fromlist=["LabelEncoder"]).LabelEncoder()

    all_teams = pd.concat([df_train["home_team"], df_train["away_team"]]).unique()
    le_team.fit(all_teams)
    le_league.fit(df_train["league"].unique())

    X = pd.DataFrame({
        "home_team_encoded": le_team.transform(df_train["home_team"]),
        "away_team_encoded": le_team.transform(df_train["away_team"]),
        "league_encoded": le_league.transform(df_train["league"]),
    })
    for f in FEATURES:
        if f not in ("home_team_encoded", "away_team_encoded", "league_encoded"):
            X[f] = df_train[f].astype(float)
    X = X[FEATURES]

    # True labels: 0=home_win, 1=draw, 2=away_win
    y = ((df_train.home_score < df_train.away_score).astype(int) * 2
         + (df_train.home_score == df_train.away_score).astype(int)).values

    print(f"Labels distribution: home={ (y==0).sum() }, draw={ (y==1).sum() }, away={ (y==2).sum() }")

    # Load trained model
    model_path = Path("models/predictor.joblib")
    if not model_path.exists():
        print(f"ERROR: {model_path} not found")
        sys.exit(1)

    model = joblib.load(model_path)
    print(f"Loaded model: {type(model).__name__}")

    # Get raw probabilities on training data
    print("Computing raw probabilities on training data...")
    raw_probs = model.predict_proba(X)
    print(f"Raw probs shape: {raw_probs.shape}")

    # Fit calibrator
    calibrator = ProbabilityCalibrator()
    calibrator.fit(raw_probs, y)
    print(f"Calibrator fitted: {calibrator.is_fitted}")

    # Save calibrator
    out_path = Path("models/calibrator.json")
    calibrator.save(out_path)
    print(f"Calibrator saved to {out_path}")

    # Verify: calibrate training probs and check Brier improvement
    cal_probs = calibrator.calibrate(raw_probs)
    from sklearn.metrics import brier_score_loss
    raw_brier = np.mean([brier_score_loss((y == i).astype(int), raw_probs[:, i]) for i in range(3)])
    cal_brier = np.mean([brier_score_loss((y == i).astype(int), cal_probs[:, i]) for i in range(3)])
    print(f"Raw Brier: {raw_brier:.4f} | Calibrated Brier: {cal_brier:.4f}")


if __name__ == "__main__":
    from train_model import engineer_features, FEATURES
    main()
