from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.isotonic import IsotonicRegression


class ProbabilityCalibrator:
    """Post-hoc calibration using isotonic regression.

    This calibrator fits one isotonic regressor per class to improve probability
    estimates. It addresses overconfidence or underconfidence in model predictions.
    """

    def __init__(self) -> None:
        self._calibrators: dict[int, IsotonicRegression] = {}
        self._n_classes: int = 0
        self._is_fitted: bool = False

    def fit(self, raw_probs: np.ndarray, y_true: np.ndarray) -> None:
        """Fit one isotonic regressor per class.

        Args:
            raw_probs: Shape (n_samples, n_classes). Raw model probabilities.
            y_true: Shape (n_samples,). Integer class labels.

        Raises:
            ValueError: If input shapes are inconsistent or insufficient data.
        """
        if raw_probs.shape[0] != len(y_true):
            raise ValueError(
                f"Number of samples mismatch: raw_probs has {raw_probs.shape[0]}, "
                f"y_true has {len(y_true)}"
            )

        if raw_probs.shape[0] < 10:
            raise ValueError(
                "Insufficient data for calibration. At least 10 samples required."
            )

        self._n_classes = raw_probs.shape[1]
        self._calibrators = {}

        for c in range(self._n_classes):
            binary_target = (y_true == c).astype(int)
            iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
            iso.fit(raw_probs[:, c], binary_target)
            self._calibrators[c] = iso

        self._is_fitted = True

    def calibrate(self, raw_probs: np.ndarray) -> np.ndarray:
        """Apply calibration and re-normalize to sum to 1.

        Args:
            raw_probs: Shape (n_samples, n_classes). Raw model probabilities.

        Returns:
            Calibrated probabilities that sum to 1 for each sample.

        Raises:
            RuntimeError: If calibrator has not been fitted.
        """
        if not self._is_fitted:
            raise RuntimeError("Calibrator must be fitted before calling calibrate.")

        calibrated = np.column_stack(
            [self._calibrators[c].predict(raw_probs[:, c]) for c in range(self._n_classes)]
        )

        row_sums = calibrated.sum(axis=1, keepdims=True)
        calibrated = calibrated / row_sums

        return calibrated

    def save(self, path: Path) -> None:
        """Save calibrator state to disk.

        Args:
            path: Path to save the calibrator state.
        """
        state = {
            "n_classes": self._n_classes,
            "is_fitted": self._is_fitted,
            "calibrators": {
                str(c): {
                    "x_min": iso.x_min,
                    "x_max": iso.x_max,
                    "x_out": iso.x_out.tolist() if hasattr(iso.x_out, "tolist") else list(iso.x_out),
                    "y_in": iso.y_in.tolist() if hasattr(iso.y_in, "tolist") else list(iso.y_in),
                    "y_out": iso.y_out.tolist() if hasattr(iso.y_out, "tolist") else list(iso.y_out),
                }
                for c, iso in self._calibrators.items()
            },
        }
        path.write_text(json.dumps(state))

    def load(self, path: Path) -> None:
        """Load calibrator state from disk.

        Args:
            path: Path to load the calibrator state from.
        """
        state = json.loads(path.read_text())
        self._n_classes = state["n_classes"]
        self._is_fitted = state["is_fitted"]
        self._calibrators = {}

        for c_str, iso_state in state["calibrators"].items():
            c = int(c_str)
            iso = IsotonicRegression(
                y_min=iso_state["x_min"], y_max=iso_state["x_max"], out_of_bounds="clip"
            )
            iso.x_min = iso_state["x_min"]
            iso.x_max = iso_state["x_max"]
            iso.x_out = np.array(iso_state["x_out"])
            iso.y_in = np.array(iso_state["y_in"])
            iso.y_out = np.array(iso_state["y_out"])
            self._calibrators[c] = iso

    def get_calibration_curve(
        self, raw_probs: np.ndarray, y_true: np.ndarray
    ) -> dict[str, Any]:
        """Compute calibration curve data for reliability diagram.

        Args:
            raw_probs: Shape (n_samples, n_classes). Raw model probabilities.
            y_true: Shape (n_samples,). Integer class labels.

        Returns:
            Dictionary with 'prob_true' (true probabilities) and 'prob_pred'
            (mean predicted probability) for each class.
        """
        if not self._is_fitted:
            raise RuntimeError("Calibrator must be fitted before computing calibration curve.")

        calibrated_probs = self.calibrate(raw_probs)
        result = {"classes": list(range(self._n_classes))}

        for c in range(self._n_classes):
            binary_target = (y_true == c).astype(int)
            pred_probs = calibrated_probs[:, c]

            bins = np.linspace(0, 1, 11)
            true_rates = []
            mean_predicted = []

            for i in range(len(bins) - 1):
                mask = (pred_probs >= bins[i]) & (pred_probs < bins[i + 1])
                if mask.sum() > 0:
                    true_rates.append(binary_target[mask].mean())
                    mean_predicted.append(pred_probs[mask].mean())

            result[f"class_{c}"] = {
                "true_probabilities": true_rates,
                "mean_predicted_probabilities": mean_predicted,
            }

        return result

    @property
    def is_fitted(self) -> bool:
        """Return whether the calibrator has been fitted."""
        return self._is_fitted
