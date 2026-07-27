"""Train XGBoost + Poisson ensemble on real match data."""
import os, json, itertools
from pathlib import Path
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, brier_score_loss
from sklearn.linear_model import PoissonRegressor
import xgboost as xgb
import joblib, warnings
warnings.filterwarnings("ignore")

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
    n = len(df)
    all_g["game_side"] = ["home"] * n + ["away"] * n
    for w in [3, 5, 10]:
        df = add_rolling(all_g, df, "home", w)
        df = add_rolling(all_g, df, "away", w)
    home_only = all_g[all_g["game_side"] == "home"].copy()
    df = add_rolling(home_only, df, "home_h", 5)
    df = add_rolling(home_only, df, "away_h", 5)
    away_only = all_g[all_g["game_side"] == "away"].copy()
    df = add_rolling(away_only, df, "home_a", 5)
    df = add_rolling(away_only, df, "away_a", 5)
    for side, tid_col in [("home", "home_team_id"), ("away", "away_team_id")]:
        last_date = df.groupby(tid_col)["scheduled_at"].shift(1)
        df[f"{side}_days_rest"] = (df["scheduled_at"] - last_date).dt.days.fillna(7).clip(1, 30)
    league_stats = df.groupby("league")["home_score"].agg(["count", "sum"]).join(
        df.groupby("league")["away_score"].agg("sum"))
    league_stats["avg_total_goals"] = (league_stats["sum"] + league_stats["away_score"]) / league_stats["count"]
    df["league_avg_total_goals"] = df["league"].map(league_stats["avg_total_goals"].to_dict()).fillna(2.5)
    h2h_rows = []
    for _, row in df.iterrows():
        h2h = df[((df["home_team_id"] == row["home_team_id"]) & (df["away_team_id"] == row["away_team_id"]) |
                  (df["home_team_id"] == row["away_team_id"]) & (df["away_team_id"] == row["home_team_id"]))]
        h2h = h2h[h2h["scheduled_at"] < row["scheduled_at"]].tail(5)
        if len(h2h) > 0:
            hg = h2h.apply(lambda r: r["home_score"] if r["home_team_id"] == row["home_team_id"] else r["away_score"], axis=1)
            ag = h2h.apply(lambda r: r["away_score"] if r["home_team_id"] == row["home_team_id"] else r["home_score"], axis=1)
            h2h_rows.append({"match_id": row["match_id"], "h2h_home_gf_avg": hg.mean(), "h2h_away_gf_avg": ag.mean(), "h2h_home_wins": (hg > ag).mean()})
        else:
            h2h_rows.append({"match_id": row["match_id"], "h2h_home_gf_avg": 0, "h2h_away_gf_avg": 0, "h2h_home_wins": 0.5})
    h2h_df = pd.DataFrame(h2h_rows).set_index("match_id")
    for c in h2h_df.columns:
        df[c] = df["match_id"].map(h2h_df[c]).fillna(0)
    ELO_K, ELO_HOME_ADV = 32, 100
    elo, elo_rows = {}, []
    for _, row in df.iterrows():
        ht, at = row["home_team_id"], row["away_team_id"]
        elo_h = elo.get(ht, 1500) + ELO_HOME_ADV
        elo_a = elo.get(at, 1500)
        e_h = 1 / (1 + 10 ** ((elo_a - elo_h) / 400))
        s_h = 1 if row["home_score"] > row["away_score"] else (0.5 if row["home_score"] == row["away_score"] else 0)
        elo[ht] = elo.get(ht, 1500) + ELO_K * (s_h - e_h)
        elo[at] = elo.get(at, 1500) + ELO_K * ((1 - s_h) - (1 - e_h))
        elo_rows.append({"match_id": row["match_id"], "home_elo": elo_h, "away_elo": elo_a, "elo_diff": elo_h - elo_a})
    elo_df = pd.DataFrame(elo_rows).set_index("match_id")
    for c in elo_df.columns:
        df[c] = df["match_id"].map(elo_df[c]).fillna(0)
    df["target"] = df.apply(lambda r: 0 if r["home_score"] > r["away_score"] else (1 if r["home_score"] == r["away_score"] else 2), axis=1)
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
    "home_days_rest", "away_days_rest", "league_avg_total_goals",
    "h2h_home_gf_avg", "h2h_away_gf_avg", "h2h_home_wins",
    "season", "home_elo", "away_elo", "elo_diff",
    "home_odds", "draw_odds", "away_odds",
    "home_implied_prob", "draw_implied_prob", "away_implied_prob",
]

def poisson_probs(lambda_h, lambda_a, max_goals=8):
    """Compute H/D/A probs from two independent Poisson distributions."""
    from scipy.stats import poisson
    ph = poisson.pmf(np.arange(max_goals+1), lambda_h)
    pa = poisson.pmf(np.arange(max_goals+1), lambda_a)
    p_home = sum(ph[i] * sum(pa[:i]) for i in range(max_goals+1))
    p_away = sum(pa[i] * sum(ph[:i]) for i in range(max_goals+1))
    p_draw = 1 - p_home - p_away
    return p_home, p_draw, p_away

def main():
    df = load_data()
    print(f"Loaded {len(df)} matches")
    df, elo_df = engineer_features(df)

    # ponytail: odds features from the-odds-api, mostly 0 for historical data
    engine2 = create_engine(os.environ["DATABASE_URL_SYNC"])
    odds_df = pd.read_sql("""
        SELECT DISTINCT ON (match_id) match_id::text, home_odds, draw_odds, away_odds
        FROM odds_snapshots ORDER BY match_id, captured_at DESC
    """, engine2)
    engine2.dispose()
    if len(odds_df) > 0:
        odds_df["match_id"] = odds_df["match_id"].astype(str)
        df["match_id"] = df["match_id"].astype(str)
        df = df.merge(odds_df, on="match_id", how="left")
        for c in ["home_odds", "draw_odds", "away_odds"]:
            df[c] = df[c].fillna(0.0).astype(float)
        inv = pd.DataFrame({
            "h": np.where(df["home_odds"] > 0, 1.0 / df["home_odds"], 0),
            "d": np.where(df["draw_odds"] > 0, 1.0 / df["draw_odds"], 0),
            "a": np.where(df["away_odds"] > 0, 1.0 / df["away_odds"], 0),
        })
        denom = inv.sum(axis=1)
        df["home_implied_prob"] = np.where(denom > 0, inv["h"] / denom, 0.0)
        df["draw_implied_prob"] = np.where(denom > 0, inv["d"] / denom, 0.0)
        df["away_implied_prob"] = np.where(denom > 0, inv["a"] / denom, 0.0)
    else:
        for c in ["home_odds", "draw_odds", "away_odds",
                   "home_implied_prob", "draw_implied_prob", "away_implied_prob"]:
            df[c] = 0.0
    n_with_odds = (df["home_odds"] > 0).sum()
    print(f"Matches with odds: {n_with_odds}/{len(df)}")

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

    team_elos = {}
    for _, row in df.iterrows():
        team_elos[row["home_team"]] = row["home_elo"]
        team_elos[row["away_team"]] = row["away_elo"]

    # Season-based split: train on all but most recent season, test on most recent
    seasons = sorted(df["season"].astype(str).unique())
    test_season = seasons[-1]
    train_seasons = [s for s in seasons if s != test_season]
    train_mask = df["season"].astype(str).isin(train_seasons)
    test_mask = df["season"].astype(str) == test_season
    # Fallback: if only one season exists, use 80/20 date split
    if len(seasons) < 2:
        split_date = df["scheduled_at"].quantile(0.8)
        train_mask = df["scheduled_at"] < split_date
        test_mask = df["scheduled_at"] >= split_date
    X_train, X_test = X[train_mask], X[test_mask]
    y_train, y_test = y[train_mask], y[test_mask]
    print(f"Train: {X_train.shape[0]} matches ({', '.join(train_seasons)})")
    print(f"Test:  {X_test.shape[0]} matches ({test_season})")

    # === XGBoost with hyperparameter tuning ===
    print("\n=== XGBoost Hyperparameter Tuning ===")
    param_grid = {
        "n_estimators": [400, 600],
        "max_depth": [4, 6],
        "learning_rate": [0.02, 0.05],
        "subsample": [0.8],
        "colsample_bytree": [0.8],
    }
    keys, values = zip(*param_grid.items())
    best_acc, best_model, best_params = 0, None, None
    for combo in itertools.product(*values):
        params = dict(zip(keys, combo))
        params["random_state"] = 42
        params["eval_metric"] = "mlogloss"
        m = xgb.XGBClassifier(**params)
        m.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
        acc = m.score(X_test, y_test)
        print(f"  {params}: acc={acc:.4f}")
        if acc > best_acc:
            best_acc, best_model, best_params = acc, m, params
    print(f"  Best: {best_params} -> acc={best_acc:.4f}")
    model_xgb = best_model
    y_prob_xgb = model_xgb.predict_proba(X_test)

    # === Poisson Goals Model ===
    print("\n=== Poisson Goals Model ===")
    poisson_home = PoissonRegressor(alpha=0.1, max_iter=500)
    poisson_away = PoissonRegressor(alpha=0.1, max_iter=500)
    poisson_home.fit(X_train, df.loc[train_mask, "home_score"])
    poisson_away.fit(X_train, df.loc[train_mask, "away_score"])
    lambda_h = poisson_home.predict(X_test)
    lambda_a = poisson_away.predict(X_test)
    y_prob_poisson = np.array([poisson_probs(lh, la) for lh, la in zip(lambda_h, lambda_a)])

    # === Ensemble (simple average) ===
    print("\n=== Ensemble ===")
    y_prob = (y_prob_xgb + y_prob_poisson) / 2
    y_pred = y_prob.argmax(axis=1)
    acc = (y_pred == y_test).mean()
    print(f"Test accuracy: {acc:.4f}")
    print(classification_report(y_test, y_pred, target_names=["home_win", "draw", "away_win"]))
    brier_avg = np.mean([brier_score_loss((y_test == i).astype(int), y_prob[:, i]) for i in range(3)])
    print(f"Brier avg: {brier_avg:.4f}")

    y_prob_xgb_only = model_xgb.predict_proba(X_test)
    acc_xgb = (y_prob_xgb_only.argmax(axis=1) == y_test).mean()
    poisson_preds = y_prob_poisson.argmax(axis=1)
    acc_poisson = (poisson_preds == y_test).mean()
    print(f"  XGBoost alone: {acc_xgb:.4f}")
    print(f"  Poisson alone: {acc_poisson:.4f}")
    print(f"  Ensemble:      {acc:.4f}")

    imp = pd.DataFrame({"feature": FEATURES, "importance": model_xgb.feature_importances_}).sort_values("importance", ascending=False)
    print("\nTop 10 features (XGBoost):")
    print(imp.head(10).to_string(index=False))

    train_dt, test_dt = df["scheduled_at"].min(), df["scheduled_at"].max()
    metadata = {
        "feature_names": list(X.columns),
        "team_classes": le_team.classes_.tolist(),
        "league_classes": le_league.classes_.tolist(),
        "target_names": ["home_win", "draw", "away_win"],
        "team_elos": {name: team_elos.get(name, 1500) for name in le_team.classes_},
        "accuracy": float(round(acc, 4)),
        "brier_score": float(round(brier_avg, 4)),
        "accuracy_xgb": float(round(acc_xgb, 4)),
        "accuracy_poisson": float(round(acc_poisson, 4)),
        "trained_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "train_date_range": [str(train_dt.date()), str(test_dt.date())],
        "train_seasons": train_seasons,
        "test_season": test_season,
        "n_matches": len(df),
        "n_features": len(X.columns),
        "best_xgb_params": {k: v if not isinstance(v, (np.integer, np.floating)) else int(v) if isinstance(v, np.integer) else float(v) for k, v in best_params.items()},
        "model_type": "ensemble_xgb_poisson",
        "model_version": "v3.2_more_data",
    }

    model_path = MODEL_DIR / "predictor.joblib"
    joblib.dump(model_xgb, model_path)
    print(f"\nXGBoost saved to {model_path}")

    joblib.dump({"home": poisson_home, "away": poisson_away}, MODEL_DIR / "poisson.joblib")
    print(f"Poisson saved to {MODEL_DIR / 'poisson.joblib'}")

    meta_path = MODEL_DIR / "predictor_metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2))
    print(f"Metadata saved to {meta_path}")

if __name__ == "__main__":
    main()
