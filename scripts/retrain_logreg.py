"""Retrain logistic regression on 8 simple features and save as predictor.joblib.

Replaces XGBoost (47 features, 46.64% acc) with logistic regression (8 features,
58.28% acc). The serving code is updated to only pass those 8 features.
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

SIMPLE_FEATURES = [
    "home_team_encoded", "away_team_encoded", "league_encoded",
    "home_gf_avg", "home_ga_avg", "away_gf_avg", "away_ga_avg",
]


def main():
    engine = create_engine(DB_URL)

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

    # Compute team stats
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

    df = df.merge(team_stats, left_on="home_team_id", right_on="team_id", how="left")
    df = df.rename(columns={"team_gf_avg": "home_gf_avg", "team_ga_avg": "home_ga_avg"})
    df = df.drop(columns=["team_id"])

    df = df.merge(team_stats, left_on="away_team_id", right_on="team_id", how="left")
    df = df.rename(columns={"team_gf_avg": "away_gf_avg", "team_ga_avg": "away_ga_avg", "team_match_count": "away_match_count"})
    df = df.drop(columns=["team_id"])

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

    # Save model
    model_path = Path("models/predictor.joblib")
    joblib.dump(lr, model_path)
    print(f"\nModel saved to {model_path}")

    # Update metadata
    meta_path = Path("models/predictor_metadata.json")
    import json
    with open(meta_path) as f:
        meta = json.load(f)

    meta["model_version"] = "v4.0_logistic"
    meta["model_type"] = "logistic_regression"
    meta["accuracy"] = float(round(lr_acc, 4))
    meta["brier_score"] = float(round(lr_brier, 4))
    meta["trained_at"] = pd.Timestamp.now(tz="UTC").isoformat()
    meta["n_matches"] = int(train_mask.sum())
    meta["n_features"] = int(X.shape[1])
    meta["feature_names"] = list(X.columns)

    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\nMetadata updated: {meta_path}")
    print(f"New accuracy: {lr_acc:.4f}, Brier: {lr_brier:.4f}")
    print(f"Model type: logistic_regression with {X.shape[1]} features")


if __name__ == "__main__":
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, brier_score_loss
    main()
