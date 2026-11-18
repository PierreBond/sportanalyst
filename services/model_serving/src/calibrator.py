from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np

# The calibration methods that can be chosen. "identity" means the model's own
# probabilities are used unchanged.
METHODS = ("identity", "isotonic", "vector")


class ProbabilityCalibrator:
    """Post-hoc calibration of match outcome probabilities.

    Three methods are available:

    ``identity``
        No calibration. A regularised logistic regression on tens of
        thousands of matches is already close to calibrated, and any
        calibration fitted on top of it can only add variance.
    ``isotonic``
        One isotonic regressor per class. Flexible, but a step function that
        overfits: on our data it made the log-loss *worse* than leaving the
        probabilities alone.
    ``vector``
        ``z_k = a_k * log(p_k) + b_k`` followed by a softmax (multiclass beta
        calibration, Kull et al. 2019). Six parameters instead of a free
        function per class.

    ``fit(..., method="auto")`` cross-validates the three methods on the
    data, keeps the one with the best held-out log-loss, and refits the
    winner on everything. The choice is therefore made out of fold.
    """

    def __init__(self, method: str = "isotonic") -> None:
        self._calibrators: dict[int, Any] = {}
        self._vector_params: tuple[np.ndarray, np.ndarray] | None = None
        self._n_classes: int = 0
        self._is_fitted: bool = False
        self._method: str = method if method in METHODS else "isotonic"

    # ------------------------------------------------------------------ fit
    def _get_isotonic(self) -> Any:
        """Lazily import IsotonicRegression, raising a helpful error if sklearn is absent."""
        try:
            from sklearn.isotonic import IsotonicRegression

            return IsotonicRegression
        except ImportError:
            raise RuntimeError(
                "scikit-learn is required for ProbabilityCalibrator. "
                "Install it with: pip install scikit-learn"
            )

    def _fit_isotonic(self, raw_probs: np.ndarray, y_true: np.ndarray) -> None:
        self._calibrators = {}
        IsotonicRegression = self._get_isotonic()
        for c in range(self._n_classes):
            binary_target = (y_true == c).astype(int)
            iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
            iso.fit(raw_probs[:, c], binary_target)
            self._calibrators[c] = iso

    def _fit_vector(self, raw_probs: np.ndarray, y_true: np.ndarray) -> None:
        """Multiclass beta calibration: z_k = a_k * log(p_k) + b_k, then softmax."""
        from scipy.optimize import minimize

        k = self._n_classes
        eps = 1e-9

        def objective(theta: np.ndarray) -> float:
            a, b = theta[:k], theta[k:]
            z = np.log(np.clip(raw_probs, eps, 1.0)) * a + b
            z -= z.max(axis=1, keepdims=True)
            p = np.exp(z)
            p /= p.sum(axis=1, keepdims=True)
            return -np.log(p[np.arange(len(y_true)), y_true]).mean()

        result = minimize(objective, np.concatenate([np.ones(k), np.zeros(k)]), method="L-BFGS-B")
        self._vector_params = (result.x[:k], result.x[k:])

    def _fit_method(self, method: str, raw_probs: np.ndarray, y_true: np.ndarray) -> None:
        if method == "isotonic":
            self._fit_isotonic(raw_probs, y_true)
        elif method == "vector":
            self._fit_vector(raw_probs, y_true)

    def fit(self, raw_probs: np.ndarray, y_true: np.ndarray, method: str = "auto") -> None:
        """Fit the calibrator.

        Args:
            raw_probs: Shape (n_samples, n_classes). Raw model probabilities.
            y_true: Shape (n_samples,). Integer class labels.
            method: ``"auto"`` (choose out of fold), ``"identity"``,
                ``"isotonic"`` or ``"vector"``.

        Raises:
            ValueError: If input shapes are inconsistent or insufficient data.
        """
        raw_probs = np.asarray(raw_probs, dtype=float)
        y_true = np.asarray(y_true, dtype=int)
        if raw_probs.shape[0] != len(y_true):
            raise ValueError(
                f"Number of samples mismatch: raw_probs has {raw_probs.shape[0]}, "
                f"y_true has {len(y_true)}"
            )
        if raw_probs.shape[0] < 10:
            raise ValueError("Insufficient data for calibration. At least 10 samples required.")

        self._n_classes = raw_probs.shape[1]
        self._calibrators = {}
        self._vector_params = None

        if method == "auto":
            method = self._select_method(raw_probs, y_true)
        if method not in METHODS:
            raise ValueError(f"Unknown calibration method {method!r}; expected one of {METHODS}")

        self._method = method
        self._fit_method(method, raw_probs, y_true)
        self._is_fitted = True

    def _select_method(self, raw_probs: np.ndarray, y_true: np.ndarray, n_splits: int = 5) -> str:
        """Pick the method with the best held-out log-loss.

        Each method is fitted on four of five blocks and scored on the fifth,
        so the comparison is out of fold. A method is only adopted over
        identity when it improves the log-loss by more than one standard
        error of the paired per-row difference: calibration that does not
        clearly help is just variance, and isotonic on this data was worse
        than leaving the probabilities alone.
        """
        n = len(y_true)
        if n < 20:
            return "identity"
        blocks = np.array_split(np.arange(n), n_splits)
        row_loss: dict[str, np.ndarray] = {}
        for candidate in METHODS:
            saved = (self._calibrators, self._vector_params, self._method)
            try:
                losses = np.empty(n)
                for block in blocks:
                    train = np.setdiff1d(np.arange(n), block)
                    self._method = candidate
                    self._fit_method(candidate, raw_probs[train], y_true[train])
                    p = self._apply(raw_probs[block])
                    losses[block] = -np.log(
                        np.clip(p[np.arange(len(block)), y_true[block]], 1e-15, 1.0)
                    )
                row_loss[candidate] = losses
            finally:
                self._calibrators, self._vector_params, self._method = saved

        baseline = row_loss["identity"]
        best = "identity"
        best_gain = 0.0
        for candidate in METHODS:
            if candidate == "identity":
                continue
            diff = baseline - row_loss[candidate]
            gain = float(diff.mean())
            stderr = float(diff.std() / np.sqrt(n))
            if gain > best_gain and gain > stderr:
                best, best_gain = candidate, gain
        return best

    # -------------------------------------------------------------- calibrate
    def _apply(self, raw_probs: np.ndarray) -> np.ndarray:
        if self._method == "isotonic":
            calibrated = np.column_stack(
                [self._calibrators[c].predict(raw_probs[:, c]) for c in range(self._n_classes)]
            )
        elif self._method == "vector":
            assert self._vector_params is not None
            a, b = self._vector_params
            z = np.log(np.clip(raw_probs, 1e-9, 1.0)) * a + b
            z -= z.max(axis=1, keepdims=True)
            calibrated = np.exp(z)
        else:
            calibrated = raw_probs
        # A zero probability is a floating-point artefact, not information.
        # Floor it so the row never sums to zero and log() stays finite.
        calibrated = np.clip(calibrated, 1e-12, 1.0)
        row_sums = calibrated.sum(axis=1, keepdims=True)
        return calibrated / row_sums

    def calibrate(self, raw_probs: np.ndarray) -> np.ndarray:
        """Apply calibration and re-normalize to sum to 1.

        Args:
            raw_probs: Shape (n_samples, n_classes). Raw model probabilities.

        Returns:
            Calibrated probabilities that sum to 1 for each sample.

        Raises:
            ValueError: If calibrator has not been fitted.
        """
        if not self._is_fitted:
            raise RuntimeError("Calibrator must be fitted before calling calibrate.")
        return self._apply(np.asarray(raw_probs, dtype=float))

    # ------------------------------------------------------------ persistence
    def save(self, path: Path) -> None:
        """Save calibrator state to disk.

        Args:
            path: Destination file path.
        """
        state = {
            "n_classes": self._n_classes,
            "is_fitted": self._is_fitted,
            "method": self._method,
            "calibrators": self._calibrators,
            "vector_params": self._vector_params,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(state, path)

    def load(self, path: Path) -> None:
        """Load calibrator state from disk.

        Args:
            path: Source file path.
        """
        state = joblib.load(path)
        self._n_classes = state["n_classes"]
        self._is_fitted = state["is_fitted"]
        # files written before the method was chosen are isotonic
        self._method = state.get("method", "isotonic")
        self._calibrators = state.get("calibrators", {})
        self._vector_params = state.get("vector_params")

    def get_calibration_curve(self, raw_probs: np.ndarray, y_true: np.ndarray) -> dict[str, Any]:
        """Compute calibration curve data for reliability diagram.

        Args:
            raw_probs: Shape (n_samples, n_classes). Raw model probabilities.
            y_true: Shape (n_samples,). Integer class labels.

        Returns:
            Dictionary with 'prob_true' (true probabilities) and 'prob_pred'
            (mean predicted probability) for each class.
        """
        calibrated_probs = self.calibrate(raw_probs)
        result: dict[str, Any] = {"classes": list(range(self._n_classes)), "method": self._method}
        y_true = np.asarray(y_true, dtype=int)

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

    @property
    def method(self) -> str:
        """The calibration method in use."""
        return self._method
