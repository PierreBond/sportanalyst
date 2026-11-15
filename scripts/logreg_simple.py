"""Logistic regression baseline vs XGBoost.

Trains both models on simple features computed directly from the database.
Tests on 2026 season. Answers: does XGBoost add value over logistic regression?
"""
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DB_URL = "postgresql://user:pass@localhost:5432/sportspred"


def main():
    engine = create_engine(DB_URL)

    # Load finished matches
    print("Loading match data...")
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT m.match_id::text, m.league, m.season,
                   m.home_score, m.away_score,
                   ht.name AS home_team, at.name AS away_team,
                   m.home_team_id, m.away_team_id
            FROM matches m
            JOIN teams ht ON ht.team_id = m.home_team_id
            JOIN teams at ON at.team_id = m.away_team_id
            WHERE m.status = 'FT' AND m.home_score IS NOT NULL
            ORDER BY m.scheduled_at
        """)).fetchall()

    print(f"Loaded {len(rows)} finished matches")

    df = pd.DataFrame(rows, columns=[
        "match_id", "league", "season", "home_score", "away_score",
        "home_team", "away_team", "home_team_id", "away_team_id"
    ])
    df["season"] = df["season"].astype(str)

    # Compute team stats: average goals for/against per team across all history
    print("Computing team stats...")
    all_games = []
    for _, row in df.iterrows():
        all_games.append({
            "team_id": row["home_team_id"], "scored": row["home_score"],
            "conceded": row["away_score"]
        })
        all_games.append({
            "team_id": row["away_team_id"], "scored": row["away_score"],
            "conceded": row["home_score"]
        })
    games_df = pd.DataFrame(all_games)

    team_stats = games_df.groupby("team_id").agg(
        team_gf_avg=("scored", "mean"),
        team_ga_avg=("conceded", "mean")
    ).reset_index()

    # Map home team stats
    df = df.merge(team_stats, left_on="home_team_id", right_on="team_id", how="left")
    df = df.rename(columns={"team_gf_avg": "home_gf_avg", "team_ga_avg": "home_ga_avg"})
    df = df.drop(columns=["team_id"])

    # Map away team stats
    df = df.merge(team_stats, left_on="away_team_id", right_on="team_id", how="left")
    df = df.rename(columns={"team_gf_avg": "away_gf_avg", "team_ga_avg": "away_ga_avg"})
    df = df.drop(columns=["team_id"])

    # Fill NaN with 0
    df[["home_gf_avg", "home_ga_avg", "away_gf_avg", "away_ga_avg"]] = \
        df[["home_gf_avg", "home_ga_avg", "away_gf_avg", "away_ga_avg"]].fillna(0)

    # Build feature matrix
    print("Building feature matrix...")
    all_team_ids = set(df["home_team_id"].unique()) | set(df["away_team_id"].unique())
    team_id_to_idx = {tid: i for i, tid in enumerate(all_team_ids)}
    league_id_to_idx = {lg: i for i, lg in enumerate(df["league"].unique())}

    X = pd.DataFrame({
        "home_team_encoded": df["home_team_id"].map(lambda t: team_id_to_idx.get(t, -1)).astype(float),
        "away_team_encoded": df["away_team_id"].map(lambda t: team_id_to_idx.get(t, -1)).astype(float),
        "league_encoded": df["league"].map(league_id_to_idx).astype(float),
        "home_gf_avg": df["home_gf_avg"].astype(float),
        "home_ga_avg": df["home_ga_avg"].astype(float),
        "away_gf_avg": df["away_gf_avg"].astype(float),
        "away_ga_avg": df["away_ga_avg"].astype(float),
    })

    y = ((df.home_score < df.away_score).astype(int) * 2
         + (df.home_score == df.away_score).astype(int)).values

    # Season split
    seasons = sorted(df["season"].unique())
    test_season = seasons[-1]
    train_mask = df["season"] != test_season
    print(f"Train seasons: {[s for s in seasons if s != test_season]}")
    print(f"Test season: {test_season}")
    print(f"Train: {train_mask.sum()}, Test: {(~train_mask).sum()}")

    X_train = X.loc[train_mask].values
    X_test = X.loc[~train_mask].values
    y_train = y[train_mask]
    y_test = y[~train_mask]

    # Logistic regression
    print("\nTraining logistic regression (L2, C=1.0)...")
    lr = LogisticRegression(max_iter=5000, random_state=42)
    lr.fit(X_train, y_train)
    lr_probs = lr.predict_proba(X_test)
    lr_preds = lr_probs.argmax(axis=1)
    lr_acc = accuracy_score(y_test, lr_preds)
    lr_brier = np.mean([brier_score_loss((y_test == i).astype(int), lr_probs[:, i]) for i in range(3)])
    print(f"Logistic regression accuracy: {lr_acc:.4f}")
    print(f"Logistic regression Brier: {lr_brier:.4f}")

    # XGBoost
    model_path = Path("models/predictor.joblib")
    if model_path.exists():
        model = joblib.load(model_path)
        if hasattr(model, "predict_proba"):
            xgb_probs = model.predict_proba(X_test)
        else:
            import xgboost as xgb
            xgb_probs = model.predict(xgb.DMatrix(X_test, feature_names=list(X_test.columns)))
        xgb_preds = xgb_probs.argmax(axis=1)
        xgb_acc = accuracy_score(y_test, xgb_preds)
        xgb_brier = np.mean([brier_score_loss((y_test == i).astype(int), xgb_probs[:, i]) for i in range(3)])
        print(f"\nXGBoost accuracy: {xgb_acc:.4f}")
        print(f"XGBoost Brier: {xgb_brier:.4f}")
        print(f"\nDifference (LR - XGB): acc={lr_acc - xgb_acc:+.4f}, brier={lr_brier - xgb_brier:+.4f}")

        print("\nPer-class accuracy:")
        for i, name in enumerate(["home_win", "draw", "away_win"]):
            mask = y_test == i
            if mask.sum() > 0:
                lr_acc_cls = (lr_preds[mask] == y_test[mask]).mean()
                raw_acc_cls = (xgb_preds[mask] == y_test[mask]).mean()
                print(f"  {name}: LR={lr_acc_cls:.4f}, XGB={raw_acc_cls:.4f} (n={mask.sum()})")
    else:
        print("predictor.joblib not found - skipping XGBoost comparison")


if __name__ == "__main__":
    main()
