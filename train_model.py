"""Train XGBoost on real match data with enriched features."""

import os, json
from pathlib import Path
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, brier_score_loss
import xgboost as xgb
import joblib

MODEL_DIR = Path(__file__).resolve().parent / "models"
MODEL_DIR.mkdir(exist_ok=True)

def load_data():
    engine = create_engine(os.environ["DATABASE_URL_SYNC"])
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
    return df

def team_games_df(df):
    home = df[["match_id", "scheduled_at", "home_team_id", "home_score", "away_score"]].copy()
    home.columns = ["match_id", "scheduled_at", "team_id", "scored", "conceded"]
    away = df[["match_id", "scheduled_at", "away_team_id", "away_score", "home_score"]].copy()
    away.columns = ["match_id", "scheduled_at", "team_id", "scored", "conceded"]
    all_g = pd.concat([home, away]).sort_values("scheduled_at").reset_index(drop=True)
    all_g["pts"] = (all_g["scored"] > all_g["conceded"]).astype(float) * 3
    all_g["pts"] += (all_g["scored"] == all_g["conceded"]).astype(float)
    return all_g

def add_rolling(all_g, df, prefix, window, game_side=None):
    g = all_g.copy()
    if game_side:
        g = g[g["game_side"] == game_side] if "game_side" in g.columns else g
    for col, name in [("scored", "gf_avg"), ("conceded", "ga_avg"), ("pts", "form")]:
        g[f"{name}_{window}"] = g.groupby("team_id")[col].transform(
            lambda x: x.shift(1).rolling(window, min_periods=1).mean())
    col_map = g.groupby("match_id").first().add_prefix(f"{prefix}_")
    for suffix in ["gf_avg", "ga_avg", "form"]:
        src = f"{prefix}_{suffix}_{window}"
        dst = f"{prefix}_{suffix}_last{window}"
        df[dst] = df["match_id"].map(col_map[src]).fillna(0)
    return df

def engineer_features(df):
    df = df.sort_values("scheduled_at").reset_index(drop=True)
    all_g = team_games_df(df)

    # mark game_side for home/away specific rolling
    n = len(df)
    all_g["game_side"] = ["home"] * n + ["away"] * n

    # rolling windows — 3, 5, 10 for all games
    for w in [3, 5, 10]:
        df = add_rolling(all_g, df, "home", w)
        df = add_rolling(all_g, df, "away", w)

    # home-specific rolling (home team's home games only)
    home_only = all_g[all_g["game_side"] == "home"].copy()
    df = add_rolling(home_only, df, "home_h", 5)
    df = add_rolling(home_only, df, "away_h", 5)

    # away-specific rolling (away team's away games only)
    away_only = all_g[all_g["game_side"] == "away"].copy()
    df = add_rolling(away_only, df, "home_a", 5)
    df = add_rolling(away_only, df, "away_a", 5)

    # days since last match
    for side, tid_col in [("home", "home_team_id"), ("away", "away_team_id")]:
        last_date = df.groupby(tid_col)["scheduled_at"].shift(1)
        df[f"{side}_days_rest"] = (df["scheduled_at"] - last_date).dt.days.fillna(7).clip(1, 30)

    # league context — avg total goals per match in league
    league_stats = df.groupby("league")["home_score"].agg(["count", "sum"]).join(
        df.groupby("league")["away_score"].agg("sum"))
    league_stats["avg_total_goals"] = (league_stats["sum"] + league_stats["away_score"]) / league_stats["count"]
    league_avg = league_stats["avg_total_goals"].to_dict()
    df["league_avg_total_goals"] = df["league"].map(league_avg).fillna(2.5)

    # h2h — last 5 meetings between same teams
    h2h_rows = []
    for _, row in df.iterrows():
        h2h = df[((df["home_team_id"] == row["home_team_id"]) & (df["away_team_id"] == row["away_team_id"]) |
                  (df["home_team_id"] == row["away_team_id"]) & (df["away_team_id"] == row["home_team_id"]))]
        h2h = h2h[h2h["scheduled_at"] < row["scheduled_at"]].tail(5)
        if len(h2h) > 0:
            home_goals = h2h.apply(lambda r: r["home_score"] if r["home_team_id"] == row["home_team_id"] else r["away_score"], axis=1)
            away_goals = h2h.apply(lambda r: r["away_score"] if r["home_team_id"] == row["home_team_id"] else r["home_score"], axis=1)
            h2h_rows.append({"match_id": row["match_id"],
                             "h2h_home_gf_avg": home_goals.mean(),
                             "h2h_away_gf_avg": away_goals.mean(),
                             "h2h_home_wins": (home_goals > away_goals).mean()})
        else:
            h2h_rows.append({"match_id": row["match_id"],
                             "h2h_home_gf_avg": 0, "h2h_away_gf_avg": 0, "h2h_home_wins": 0.5})
    h2h_df = pd.DataFrame(h2h_rows).set_index("match_id")
    for c in h2h_df.columns:
        df[c] = df["match_id"].map(h2h_df[c]).fillna(0)

    # Elo ratings (sequential, chronological)
    ELO_K = 32
    ELO_HOME_ADV = 100
    elo = {}
    elo_ratings = []
    for _, row in df.iterrows():
        ht, at = row["home_team_id"], row["away_team_id"]
        elo_h = elo.get(ht, 1500) + ELO_HOME_ADV
        elo_a = elo.get(at, 1500)
        e_h = 1 / (1 + 10 ** ((elo_a - elo_h) / 400))
        e_a = 1 - e_h
        s_h = 1 if row["home_score"] > row["away_score"] else (0.5 if row["home_score"] == row["away_score"] else 0)
        s_a = 1 - s_h
        elo[ht] = elo.get(ht, 1500) + ELO_K * (s_h - e_h)
        elo[at] = elo.get(at, 1500) + ELO_K * (s_a - e_a)
        elo_ratings.append({"match_id": row["match_id"], "home_elo": elo_h, "away_elo": elo_a, "elo_diff": elo_h - elo_a})
    elo_df = pd.DataFrame(elo_ratings).set_index("match_id")
    for c in elo_df.columns:
        df[c] = df["match_id"].map(elo_df[c]).fillna(0)

    df["target"] = df.apply(
        lambda r: 0 if r["home_score"] > r["away_score"]
                  else (1 if r["home_score"] == r["away_score"] else 2), axis=1)
    return df, elo_df

FEATURES = [
    "home_team_encoded", "away_team_encoded", "league_encoded",
    "home_gf_avg_last3", "home_ga_avg_last3", "home_form_last3",
    "home_gf_avg_last5", "home_ga_avg_last5", "home_form_last5",
    "home_gf_avg_last10", "home_ga_avg_last10", "home_form_last10",
    "away_gf_avg_last3", "away_ga_avg_last3", "away_form_last3",
    "away_gf_avg_last5", "away_ga_avg_last5", "away_form_last5",
    "away_gf_avg_last10", "away_ga_avg_last10", "away_form_last10",
    "home_h_gf_avg_last5", "home_h_ga_avg_last5", "home_h_form_last5",
    "away_a_gf_avg_last5", "away_a_ga_avg_last5", "away_a_form_last5",
    "home_days_rest", "away_days_rest",
    "league_avg_total_goals",
    "h2h_home_gf_avg", "h2h_away_gf_avg", "h2h_home_wins",
    "season",
    "home_elo", "away_elo", "elo_diff",
]

def main():
    df = load_data()
    print(f"Loaded {len(df)} matches")
    df, elo_df = engineer_features(df)
    df = df.dropna(subset=["target"])
    print(f"After features: {len(df)} matches")
    print(f"Target distribution: {df['target'].value_counts().to_dict()}")

    le_team = LabelEncoder()
    all_teams = pd.concat([df["home_team"], df["away_team"]]).unique()
    le_team.fit(all_teams)
    le_league = LabelEncoder()
    le_league.fit(df["league"])

    X = pd.DataFrame({
        "home_team_encoded": le_team.transform(df["home_team"]),
        "away_team_encoded": le_team.transform(df["away_team"]),
        "league_encoded": le_league.transform(df["league"]),
        **{f: df[f].astype(float) for f in FEATURES if f not in ["home_team_encoded", "away_team_encoded", "league_encoded"]},
    })
    X = X[FEATURES]
    y = df["target"]

    # extract final Elo ratings for each team from the last match they played
    team_elos = {}
    for _, row in df.iterrows():
        team_elos[row["home_team"]] = row["home_elo"]
        team_elos[row["away_team"]] = row["away_elo"]

    # time-based split: train on older matches, test on recent
    split_date = df["scheduled_at"].quantile(0.8)
    train_idx = df["scheduled_at"] < split_date
    test_idx = df["scheduled_at"] >= split_date
    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]

    model = xgb.XGBClassifier(
        n_estimators=600, max_depth=6, learning_rate=0.03,
        subsample=0.8, colsample_bytree=0.8, random_state=42,
        eval_metric="mlogloss",
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)
    acc = model.score(X_test, y_test)
    print(f"\nTest accuracy: {acc:.3f}")
    print(classification_report(y_test, y_pred, target_names=["home_win", "draw", "away_win"]))
    for i, label in enumerate(["home", "draw", "away"]):
        brier = brier_score_loss((y_test == i).astype(int), y_prob[:, i])
        print(f"  Brier ({label}): {brier:.4f}")

    # feature importance
    imp = pd.DataFrame({"feature": FEATURES, "importance": model.feature_importances_}).sort_values("importance", ascending=False)
    print("\nTop 10 features:")
    print(imp.head(10).to_string(index=False))

    train_dt = df["scheduled_at"].min()
    test_dt = df["scheduled_at"].max()
    brier_avg = (sum(brier_score_loss((y_test == i).astype(int), y_prob[:, i]) for i in range(3))) / 3
    metadata = {
        "feature_names": list(X.columns),
        "team_classes": le_team.classes_.tolist(),
        "league_classes": le_league.classes_.tolist(),
        "target_names": ["home_win", "draw", "away_win"],
        "team_elos": {name: team_elos.get(name, 1500) for name in le_team.classes_},
        "accuracy": float(round(model.score(X_test, y_test), 4)),
        "brier_score": float(round(brier_avg, 4)),
        "trained_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "train_date_range": [str(train_dt.date()), str(test_dt.date())],
        "n_matches": len(df),
        "n_features": len(X.columns),
    }

    model_path = MODEL_DIR / "predictor.joblib"
    joblib.dump(model, model_path)
    print(f"\nModel saved to {model_path}")
    meta_path = MODEL_DIR / "predictor_metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2))
    print(f"Metadata saved to {meta_path}")

if __name__ == "__main__":
    main()
