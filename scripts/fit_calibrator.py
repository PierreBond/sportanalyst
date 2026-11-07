"""Fit the probability calibrator on historical (pre-2026) data and save it.

Uses the model's training-season split (seasons[:-1]) so the calibrator is
fit on data the model already saw, then applied to future predictions.
Avoids the 2026 test season entirely to prevent leakage.
"""
import sys
from pathlib import Path

import joblib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "libs"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backtest_markets import build_test_frame
from services.model_serving.src.calibrator import ProbabilityCalibrator


def main() -> None:
    df, X, train_mask, _test_mask = build_test_frame()

    # Calibration data = seasons before the test season (what model was trained on)
    cal_df = df.loc[train_mask].reset_index(drop=True)
    cal_X = X.loc[train_mask].reset_index(drop=True)

    # Labels: 0=home win, 1=draw, 2=away win
    y = ((cal_df.home_score < cal_df.away_score).astype(int) * 2
         + (cal_df.home_score == cal_df.away_score).astype(int)).values

    model = joblib.load(Path(__file__).resolve().parent.parent / "models" / "predictor.joblib")
    raw_probs = model.predict_proba(cal_X)

    calibrator = ProbabilityCalibrator()
    calibrator.fit(raw_probs, y)

    out = Path(__file__).resolve().parent.parent / "models" / "calibrator.json"
    calibrator.save(out)
    print(f"calibrator fitted on {len(y)} samples, saved to {out}")


if __name__ == "__main__":
    main()
