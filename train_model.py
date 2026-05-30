"""Train sklearn GradientBoosting model on historical match data."""
import os, sys, asyncio, json
from pathlib import Path
import numpy as np
import pandas as pd
from sqlalchemy import text
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import GradientBoostingClassifier
import joblib

os.environ["DATABASE_URL"] = "postgresql+asyncpg://user:pass@localhost:5432/sportspred"
os.environ["DATABASE_URL_SYNC"] = "postgresql://user:pass@localhost:5432/sportspred"

sys.path.insert(0, str(Path(__file__).resolve().parent / "libs"))
from sports_common.db import db_client

MODEL_DIR = Path(__file__).resolve().parent / "models"
MODEL_DIR.mkdir(exist_ok=True)

async def load_data():
    await db_client.init_db()
    async with db_client.session() as session:
        result = await session.execute(text("""
            SELECT
                m.external_id, m.league, m.season, m.round,
                ht.name AS home_team_name,
                at.name AS away_team_name,
                m.home_score, m.away_score
            FROM matches m
            JOIN teams ht ON ht.team_id = m.home_team_id
            JOIN teams at ON at.team_id = m.away_team_id
            WHERE m.home_score IS NOT NULL AND m.away_score IS NOT NULL
        """))
        rows = result.mappings().all()
    return pd.DataFrame(rows)

def engineer_features(df):
    df = df.copy()
    df["home_goals"] = df["home_score"].astype(float)
    df["away_goals"] = df["away_score"].astype(float)

    df["target"] = df.apply(
        lambda r: 0 if r["home_goals"] > r["away_goals"]
                  else (1 if r["home_goals"] == r["away_goals"] else 2),
        axis=1,
    )

    le_team = LabelEncoder()
    all_teams = pd.concat([df["home_team_name"], df["away_team_name"]]).unique()
    le_team.fit(all_teams)

    le_league = LabelEncoder()
    le_league.fit(df["league"])

    features = pd.DataFrame({
        "home_team_encoded": le_team.transform(df["home_team_name"]),
        "away_team_encoded": le_team.transform(df["away_team_name"]),
        "league_encoded": le_league.transform(df["league"]),
        "season": df["season"].astype(int),
    })

    metadata = {
        "feature_names": list(features.columns),
        "team_classes": le_team.classes_.tolist(),
        "league_classes": le_league.classes_.tolist(),
        "target_names": ["home_win", "draw", "away_win"],
    }

    return features, df["target"], metadata

def main():
    df = asyncio.run(load_data())
    print(f"Loaded {len(df)} matches")

    if len(df) < 100:
        print(f"Only {len(df)} samples, need at least 100")
        return

    X, y, metadata = engineer_features(df)
    print(f"Features: {list(X.columns)}")
    print(f"Target distribution: {y.value_counts().to_dict()}")

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    model = GradientBoostingClassifier(
        n_estimators=200, max_depth=5, learning_rate=0.1,
        subsample=0.8, random_state=42,
    )
    model.fit(X_train, y_train)

    acc = model.score(X_test, y_test)
    print(f"Test accuracy: {acc:.3f}")

    from sklearn.metrics import classification_report
    y_pred = model.predict(X_test)
    print(classification_report(y_test, y_pred, target_names=metadata["target_names"]))

    model_path = MODEL_DIR / "predictor.joblib"
    joblib.dump(model, model_path)
    print(f"Model saved to {model_path}")

    meta_path = MODEL_DIR / "predictor_metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2))
    print(f"Metadata saved to {meta_path}")

if __name__ == "__main__":
    main()
