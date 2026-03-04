from __future__ import annotations

import abc
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class ModelMeta:
    name: str
    version: str
    hyperparameters: dict[str, Any]


class BaseModel(abc.ABC):
    """Abstract base for all prediction models."""

    meta: ModelMeta

    @abc.abstractmethod
    def train(self, X_train: pd.DataFrame, y_train: pd.Series) -> None:
        """Train the model on the provided data."""
        ...

    @abc.abstractmethod
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Return probability estimates. Shape: (n_samples, n_classes).
        Classes: [home_win, draw, away_win] for match-outcome models.
        """
        ...

    @abc.abstractmethod
    def save(self, path: Path) -> None:
        """Serialize model to disk."""
        ...

    @abc.abstractmethod
    def load(self, path: Path) -> None:
        """Deserialize model from disk."""
        ...

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Return class predictions."""
        probas = self.predict_proba(X)
        return np.argmax(probas, axis=1)

    def get_feature_importance(self) -> dict[str, float] | None:
        """Return feature importances if the model supports it."""
        return None

    def get_params(self) -> dict[str, Any]:
        """Get model parameters."""
        return self.meta.hyperparameters

    def set_params(self, **params: Any) -> None:
        """Set model parameters."""
        self.meta.hyperparameters.update(params)
