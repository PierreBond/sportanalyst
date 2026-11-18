"""Retrain the served model end to end: logistic regression + goal models + calibrator.

Everything here is aligned with what the serving layer does per request
(services/model_serving/src/main.py::_build_features_for_match): same feature
names, same semantics, and rolling stats that only look at matches played
before the fixture. The previous model was trained on season averages computed
over the whole dataset, and the calibrator on file belonged to the older
gradient-boosted model, so the served numbers drifted away from both.

Club history is keyed on the canonical club name, so a club stored under
several team_ids ("Marseille", "Olympique de Marseille") is rated on its full
history rather than one id's slice.

Artifacts written to models/:
  predictor.joblib        served logistic regression pipeline
  predictor_metadata.json feature names, encodings, elos, metrics, blend weight
  poisson.joblib          goal-count regressors behind xG / totals / BTTS
  calibrator.json         isotonic calibration fitted out-of-fold
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.linear_model import LogisticRegression, PoissonRegressor
from sklearn.metrics import brier_score_loss, mean_absolute_error
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "libs"))

from services.model_serving.src.calibrator import ProbabilityCalibrator  # noqa: E402
from train_model import FEATURES as POISSON_FEATURES  # noqa: E402
from train_model import (  # noqa: E402
    engineer_features,
    final_team_elos,
    load_data,
    poisson_probs,
)

MODEL_DIR = ROOT / "models"

# Every name below is produced by the serving feature builder.
LR_FEATURES = [
    "elo_diff",
    "home_gf_avg_last5",
    "home_ga_avg_last5",
    "away_gf_avg_last5",
    "away_ga_avg_last5",
    "home_form_last5",
    "away_form_last5",
    "home_days_rest",
    "away_days_rest",
    "league_avg_total_goals",
    "league_draw_rate",
]

# The board compares the model with the market, so the served model must not
# read the market: no odds, no implied probabilities.
MARKET_FEATURES = {"home_odds", "draw_odds", "away_odds",
                   "home_implied_prob", "draw_implied_prob", "away_implied_prob"}


def merge_odds(df: pd.DataFrame) -> pd.DataFrame:
    """Attach the latest odds snapshot per match (same source as train_model)."""
    from sqlalchemy import create_engine, text

    url = os.environ.get(
        "DATABASE_URL_SYNC", "postgresql://user:pass@localhost:5432/sportspred"
    )
    engine = create_engine(url)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT DISTINCT ON (match_id) match_id::text AS match_id,
                       home_odds, draw_odds, away_odds
                FROM odds_snapshots ORDER BY match_id, captured_at DESC
                """
            )
        ).fetchall()
    engine.dispose()

    odds = pd.DataFrame(
        rows, columns=["match_id", "home_odds", "draw_odds", "away_odds"]
    )
    out = df.copy()
    out["match_id"] = out["match_id"].astype(str)
    out = out.merge(odds, on="match_id", how="left")
    for col in ("home_odds", "draw_odds", "away_odds"):
        out[col] = out[col].fillna(0.0).astype(float)

    inv = pd.DataFrame(
        {
            "h": np.where(out["home_odds"] > 0, 1.0 / out["home_odds"], 0.0),
            "d": np.where(out["draw_odds"] > 0, 1.0 / out["draw_odds"], 0.0),
            "a": np.where(out["away_odds"] > 0, 1.0 / out["away_odds"], 0.0),
        }
    )
    denom = inv.sum(axis=1)
    out["home_implied_prob"] = np.where(denom > 0, inv["h"] / denom, 0.0)
    out["draw_implied_prob"] = np.where(denom > 0, inv["d"] / denom, 0.0)
    out["away_implied_prob"] = np.where(denom > 0, inv["a"] / denom, 0.0)
    return out


def multiclass_brier(y_true: np.ndarray, probs: np.ndarray) -> float:
    return float(
        np.mean(
            [
                brier_score_loss((y_true == i).astype(int), probs[:, i])
                for i in range(probs.shape[1])
            ]
        )
    )


def goal_probabilities(lam_h: np.ndarray, lam_a: np.ndarray) -> np.ndarray:
    return np.array([poisson_probs(lh, la) for lh, la in zip(lam_h, lam_a)])


def main() -> None:
    os.environ.setdefault(
        "DATABASE_URL_SYNC", "postgresql://user:pass@localhost:5432/sportspred"
    )

    print("Loading matches...")
    df = load_data()
    print(f"Loaded {len(df)} matches")

    print("Engineering leak-free features (a few minutes)...")
    df, _ = engineer_features(df)
    df = merge_odds(df)
    df = df.dropna(subset=["target"]).reset_index(drop=True)

    seasons = sorted(df["season"].astype(str).unique())
    test_season = seasons[-1]
    train_seasons = [s for s in seasons if s != test_season]
    train_mask = (df["season"].astype(str) != test_season).values

    y = df["target"].astype(int).values

    # --- encodings: canonical club names, same order the serving layer reads ---
    le_team = LabelEncoder()
    le_team.fit(pd.concat([df["home_team"], df["away_team"]]).unique())
    le_league = LabelEncoder()
    le_league.fit(df["league"])
    team_classes = list(le_team.classes_)
    league_classes = list(le_league.classes_)

    def feature_frame(features: list[str]) -> pd.DataFrame:
        frame = pd.DataFrame(index=df.index)
        frame["home_team_encoded"] = le_team.transform(df["home_team"]).astype(float)
        frame["away_team_encoded"] = le_team.transform(df["away_team"]).astype(float)
        frame["league_encoded"] = le_league.transform(df["league"]).astype(float)
        for name in features:
            if name in frame.columns:
                continue
            frame[name] = df[name].astype(float)
        return frame[features]

    # --- goal models -------------------------------------------------------
    # The goal model feeds both the 1X2 blend and the xG / totals / BTTS
    # markets. The market-informed variant is measured for information only:
    # the served model must not read the price it is later compared against.
    goal_variants = {
        "full": POISSON_FEATURES,
        "no_market": [f for f in POISSON_FEATURES if f not in MARKET_FEATURES],
        "no_market_no_enc": [
            f
            for f in POISSON_FEATURES
            if f not in MARKET_FEATURES
            and f not in ("home_team_encoded", "away_team_encoded", "season")
        ],
    }

    best_goal: tuple[float, float, str, list[str]] | None = None
    goal_probs_by_variant: dict[str, np.ndarray] = {}
    for name, features in goal_variants.items():
        frame = feature_frame(features)
        home_model = PoissonRegressor(alpha=0.1, max_iter=500)
        away_model = PoissonRegressor(alpha=0.1, max_iter=500)
        home_model.fit(frame[train_mask], df.loc[train_mask, "home_score"])
        away_model.fit(frame[train_mask], df.loc[train_mask, "away_score"])
        lam_h = home_model.predict(frame)
        lam_a = away_model.predict(frame)
        probs = goal_probabilities(lam_h, lam_a)
        goal_probs_by_variant[name] = probs

        val_h_mae = mean_absolute_error(df.loc[~train_mask, "home_score"], lam_h[~train_mask])
        val_a_mae = mean_absolute_error(df.loc[~train_mask, "away_score"], lam_a[~train_mask])
        acc = float((probs[~train_mask].argmax(1) == y[~train_mask]).mean())
        brier = multiclass_brier(y[~train_mask], probs[~train_mask])
        market_free = name != "full"
        print(
            f"  goal[{name}] n_feat={len(features)} goal_mae={val_h_mae:.3f}/{val_a_mae:.3f} "
            f"acc={acc:.4f} brier={brier:.4f}{'' if market_free else ' (market-informed, not selectable)'}"
        )
        # Select on what the goal model is actually used for: 1X2 quality.
        # Goal-count MAE barely separates the variants; accuracy does.
        if not market_free:
            continue
        score = (acc, -brier, -len(features))
        if best_goal is None or score > best_goal[:3]:
            best_goal = (acc, -brier, name, features)

    goal_name = best_goal[2] if best_goal else "no_market"
    goal_features = goal_variants[goal_name]
    goal_probs = goal_probs_by_variant[goal_name]
    print(f"  -> goal model variant: {goal_name} ({len(goal_features)} features)")

    goal_frame = feature_frame(goal_features)
    poisson_home = PoissonRegressor(alpha=0.1, max_iter=500)
    poisson_away = PoissonRegressor(alpha=0.1, max_iter=500)
    poisson_home.fit(goal_frame[train_mask], df.loc[train_mask, "home_score"])
    poisson_away.fit(goal_frame[train_mask], df.loc[train_mask, "away_score"])

    # --- logistic regression ----------------------------------------------
    X = df[LR_FEATURES].astype(float)
    model = Pipeline(
        [
            ("scale", StandardScaler()),
            ("lr", LogisticRegression(max_iter=5000, C=1.0, random_state=42)),
        ]
    )
    model.fit(X[train_mask], y[train_mask])
    print(f"Fitted logistic regression on {int(train_mask.sum())} matches")

    lr_val = model.predict_proba(X[~train_mask])
    goal_val = goal_probs[~train_mask]
    y_val = y[~train_mask]

    print(f"\nValidation season {test_season} ({len(y_val)} matches)")
    print(f"  logistic alone: acc={(lr_val.argmax(1) == y_val).mean():.4f} "
          f"brier={multiclass_brier(y_val, lr_val):.4f}")
    print(f"  goal model alone: acc={(goal_val.argmax(1) == y_val).mean():.4f} "
          f"brier={multiclass_brier(y_val, goal_val):.4f}")

    best_weight, best_acc, best_brier = 1.0, -1.0, 9.9
    for weight in (0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
        probs = weight * lr_val + (1.0 - weight) * goal_val
        acc = float((probs.argmax(1) == y_val).mean())
        brier = multiclass_brier(y_val, probs)
        print(f"  blend w={weight:.1f}: acc={acc:.4f} brier={brier:.4f}")
        if (acc, -brier) > (best_acc, -best_brier):
            best_weight, best_acc, best_brier = weight, acc, brier
    print(f"  -> blend weight {best_weight:.1f}")

    # Calibrator fitted out-of-fold on the training seasons only, so the
    # validation season stays untouched.
    print("\nFitting calibrator out-of-fold...")
    oof = np.zeros((int(train_mask.sum()), 3))
    goal_train = goal_probs[train_mask]
    splitter = TimeSeriesSplit(n_splits=5)
    for fold_train, fold_val in splitter.split(X[train_mask]):
        fold_model = clone(model).fit(X[train_mask].iloc[fold_train], y[train_mask][fold_train])
        fold_probs = fold_model.predict_proba(X[train_mask].iloc[fold_val])
        oof[fold_val] = (
            best_weight * fold_probs + (1.0 - best_weight) * goal_train[fold_val]
        )

    calibrator = ProbabilityCalibrator()
    calibrator.fit(oof, y[train_mask])
    calibrator.save(MODEL_DIR / "calibrator.json")

    served_val = best_weight * lr_val + (1.0 - best_weight) * goal_val
    calibrated_val = calibrator.calibrate(served_val)
    final_acc = float((calibrated_val.argmax(1) == y_val).mean())
    final_brier = multiclass_brier(y_val, calibrated_val)
    base_rate = float(np.bincount(y_val, minlength=3).max() / len(y_val))

    print(f"\nServed model on {test_season}: accuracy={final_acc:.4f} brier={final_brier:.4f}")
    print(f"  majority-class base rate: {base_rate:.4f}")
    from sklearn.metrics import classification_report

    print(classification_report(y_val, calibrated_val.argmax(1), target_names=["home_win", "draw", "away_win"]))

    joblib.dump(model, MODEL_DIR / "predictor.joblib")
    joblib.dump({"home": poisson_home, "away": poisson_away}, MODEL_DIR / "poisson.joblib")

    meta_path = MODEL_DIR / "predictor_metadata.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    meta.update(
        {
            "feature_names": LR_FEATURES,
            "poisson_feature_names": goal_features,
            "team_classes": team_classes,
            "league_classes": league_classes,
            "team_elos": final_team_elos(df),
            # Bump on every retrain: the batch upsert only replaces stored
            # predictions when the model version differs, so a reused version
            # leaves rows from the previous artifact in the table.
            "model_version": "v4.4_logistic",
            "model_type": "logistic_regression",
            "accuracy": float(round(final_acc, 4)),
            "brier_score": float(round(final_brier, 4)),
            "accuracy_base_rate": float(round(base_rate, 4)),
            "accuracy_raw": float(round(best_acc, 4)),
            "brier_raw": float(round(best_brier, 4)),
            "accuracy_poisson": float(
                round(float((goal_val.argmax(1) == y_val).mean()), 4)
            ),
            "blend_sweep_best": {
                "weight_xgb": float(best_weight),
                "accuracy": float(round(best_acc, 4)),
                "brier": float(round(best_brier, 4)),
            },
            "goal_model_variant": goal_name,
            "trained_at": pd.Timestamp.now(tz="UTC").isoformat(),
            "n_matches": int(train_mask.sum()),
            "n_features": len(LR_FEATURES),
            "train_seasons": train_seasons,
            "test_season": test_season,
            "train_date_range": [
                str(df["scheduled_at"].min().date()),
                str(df["scheduled_at"].max().date()),
            ],
        }
    )
    meta_path.write_text(json.dumps(meta, indent=2))
    print(f"\nSaved model, goal models, metadata and calibrator to {MODEL_DIR}")


if __name__ == "__main__":
    main()
