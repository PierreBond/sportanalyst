from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import f1_score, roc_auc_score, brier_score_loss, accuracy_score

from .base_model import BaseModel, ModelMeta
from sports_common.logging import get_logger

logger = get_logger(__name__)


class InjuryRiskModel(BaseModel):
    """XGBoost classifier for injury risk prediction.

    Predicts probability of injury in the next 7 days based on:
    - ACWR (7/28 day ratio)
    - Rolling HRV (7-day average)
    - Resting HR trend
    - Sleep quality score
    - Cumulative PlayerLoad (season)

    Target: >= 85% F1 macro on held-out test set.
    """

    def __init__(
        self,
        meta: ModelMeta | None = None,
        **hyperparameters: Any,
    ) -> None:
        if meta is None:
            meta = ModelMeta(
                name="injury_risk_xgboost",
                version="1.0.0",
                hyperparameters=hyperparameters,
            )
        self.meta = meta

        default_params = {
            "n_estimators": 200,
            "max_depth": 5,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "min_child_weight": 3,
            "scale_pos_weight": 1,
            "objective": "binary:logistic",
            "eval_metric": "logloss",
            "use_label_encoder": False,
        }
        default_params.update(hyperparameters)
        self._params = default_params
        self._model: xgb.XGBClassifier | None = None
        self._feature_names: list[str] | None = None

    def train(self, X_train: pd.DataFrame, y_train: pd.Series) -> None:
        """Train the XGBoost injury risk model."""
        self._feature_names = list(X_train.columns)

        class_counts = y_train.value_counts()
        if len(class_counts) > 1:
            neg_count = class_counts.get(0, 1)
            pos_count = class_counts.get(1, 1)
            self._params["scale_pos_weight"] = neg_count / pos_count

        self._model = xgb.XGBClassifier(**self._params)
        self._model.fit(
            X_train,
            y_train,
            eval_set=[(X_train, y_train)],
            verbose=False,
        )

        logger.info(
            "injury_risk_model_trained",
            n_samples=len(X_train),
            features=self._feature_names,
        )

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Return injury probability. Shape: (n_samples, 2) [no_injury, injury]."""
        if self._model is None:
            raise ValueError("Model not trained. Call train() first.")

        proba = self._model.predict_proba(X)
        return proba

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Return binary injury predictions."""
        if self._model is None:
            raise ValueError("Model not trained. Call train() first.")
        return self._model.predict(X)

    def predict_injury_probability(self, X: pd.DataFrame) -> np.ndarray:
        """Return just the injury probability (for binary classification)."""
        proba = self.predict_proba(X)
        return proba[:, 1]

    def save(self, path: Path) -> None:
        """Serialize model to disk."""
        if self._model is None:
            raise ValueError("Model not trained. Cannot save.")

        model_data = {
            "model": self._model,
            "meta": self.meta,
            "feature_names": self._feature_names,
            "params": self._params,
        }

        import joblib
        joblib.dump(model_data, path)
        logger.info("injury_risk_model_saved", path=str(path))

    def load(self, path: Path) -> None:
        """Deserialize model from disk."""
        import joblib
        model_data = joblib.load(path)

        self._model = model_data["model"]
        self.meta = model_data["meta"]
        self._feature_names = model_data["feature_names"]
        self._params = model_data["params"]

        logger.info("injury_risk_model_loaded", path=str(path))

    def get_feature_importance(self) -> dict[str, float] | None:
        """Return feature importances."""
        if self._model is None:
            return None

        importances = self._model.feature_importances_
        if self._feature_names is None:
            return None

        return {
            name: float(importances[i])
            for i, name in enumerate(self._feature_names)
        }


def compute_evaluation_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: np.ndarray,
) -> dict[str, float]:
    """Compute evaluation metrics for injury risk model."""
    metrics = {}

    metrics["accuracy"] = accuracy_score(y_true, y_pred)
    metrics["f1_macro"] = f1_score(y_true, y_pred, average="macro")
    metrics["f1_positive"] = f1_score(y_true, y_pred, average="binary")

    try:
        metrics["roc_auc"] = roc_auc_score(y_true, y_proba)
    except ValueError:
        metrics["roc_auc"] = 0.0

    metrics["brier_score"] = brier_score_loss(y_true, y_proba)

    return metrics
