"""Backtest Poisson goal markets (xG, O/U, BTTS, correct score) on the test season.

Mirrors train_model.py exactly: same features, same odds merge, same
season split (train on older seasons, evaluate on the latest season).
"""
import os
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from sklearn.linear_model import PoissonRegressor

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from train_model import load_data, engineer_features


def build_test_frame():
    """Shared pipeline: load, engineer, merge odds, split seasons.
    Used by this script and backtest_value_bets.py."""
    df = load_data()
    df, _elo = engineer_features(df)

    engine = create_engine(os.environ["DATABASE_URL_SYNC"])
    odds_df = pd.read_sql("""
        SELECT DISTINCT ON (match_id) match_id::text, home_odds, draw_odds, away_odds
        FROM odds_snapshots ORDER BY match_id, captured_at DESC
    """, engine)
    engine.dispose()
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

    from sklearn.preprocessing import LabelEncoder
    from train_model import FEATURES

    le_team = LabelEncoder()
    le_team.fit(pd.concat([df["home_team"], df["away_team"]]).unique())
    le_league = LabelEncoder()
    le_league.fit(df["league"])
    X = pd.DataFrame({
        "home_team_encoded": le_team.transform(df["home_team"]),
        "away_team_encoded": le_team.transform(df["away_team"]),
        "league_encoded": le_league.transform(df["league"]),
        **{f: df[f].astype(float) for f in FEATURES if f not in ["home_team_encoded", "away_team_encoded", "league_encoded"]},
    })
    X = X[FEATURES]

    seasons = sorted(df["season"].astype(str).unique())
    test_season = seasons[-1]
    train_mask = df["season"].astype(str).isin(seasons[:-1])
    test_mask = df["season"].astype(str) == test_season
    return df, X, train_mask, test_mask


def main():
    df, X, train_mask, test_mask = build_test_frame()
    test_season = df.loc[test_mask, "season"].astype(str).iloc[0]
    print(f"Test season: {test_season} ({test_mask.sum()} matches)")

    poisson_home = PoissonRegressor(alpha=0.1, max_iter=500)
    poisson_away = PoissonRegressor(alpha=0.1, max_iter=500)
    poisson_home.fit(X[train_mask], df.loc[train_mask, "home_score"])
    poisson_away.fit(X[train_mask], df.loc[train_mask, "away_score"])

    lam_h = np.clip(poisson_home.predict(X[test_mask]), 0.05, 6.0)
    lam_a = np.clip(poisson_away.predict(X[test_mask]), 0.05, 6.0)
    total = lam_h + lam_a
    yt = df.loc[test_mask, "home_score"].astype(float)
    xta = df.loc[test_mask, "away_score"].astype(float)
    actual_total = yt + xta
    actual_btts = ((yt > 0) & (xta > 0)).astype(float).to_numpy()

    from scipy.stats import poisson as ps

    print("\n=== Totals backtest (test season, out-of-sample) ===")
    for line in [0.5, 1.5, 2.5, 3.5]:
        p_over = np.array([1.0 - ps.cdf(int(line), t) for t in total])
        actual_over = (actual_total > line).astype(float).to_numpy()
        b = np.mean((p_over - actual_over) ** 2)
        acc = float(((p_over > 0.5) == (actual_over == 1)).mean())
        base = float(max((actual_over == 1).mean(), (actual_over == 0).mean()))
        print(f"O/U {line}: acc={acc:.4f} brier={b:.4f} (always-over/under baseline acc={base:.4f})")

    print("\n=== BTTS backtest ===")
    p_btts = (1 - np.exp(-lam_h)) * (1 - np.exp(-lam_a))
    b = np.mean((p_btts - actual_btts) ** 2)
    acc = float(((p_btts > 0.5) == (actual_btts == 1)).mean())
    base = float(max(actual_btts.mean(), 1 - actual_btts.mean()))
    print(f"BTTS: acc={acc:.4f} brier={b:.4f} (baseline acc={base:.4f})")

    print("\n=== 1X2 from goal matrix (informational, compare with XGB 0.4664) ===")
    max_goals = 8
    p_h, p_d, p_a = [], [], []
    for i in range(len(lam_h)):
        mh = ps.pmf(np.arange(max_goals + 1), lam_h[i])
        ma = ps.pmf(np.arange(max_goals + 1), lam_a[i])
        mm = np.outer(mh, ma)
        p_h.append(np.tril(mm, -1).sum())
        p_d.append(np.trace(mm))
        p_a.append(np.triu(mm, 1).sum())
    p_h, p_d, p_a = np.array(p_h), np.array(p_d), np.array(p_a)
    y_actual = np.where(yt > xta, 0, np.where(yt == xta, 1, 2))
    pred = np.argmax(np.column_stack([p_h, p_d, p_a]), axis=1)
    acc = float((pred == y_actual).mean())
    p_sum = p_h + p_d + p_a
    b = float(np.mean(np.sum(((np.column_stack([p_h, p_d, p_a]) / p_sum[:, None]) - np.eye(3)[y_actual]) ** 2, axis=1)))
    print(f"Goal-poisson 1X2: acc={acc:.4f} brier={b:.4f}")


if __name__ == "__main__":
    main()
