from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


class XGBoostModel:
    """XGBoost model wrapper for match outcome prediction."""

    def __init__(self, params: dict | None = None) -> None:
        self._params = params or {
            "n_estimators": 100,
            "max_depth": 6,
            "learning_rate": 0.1,
            "objective": "multi:softprob",
            "num_class": 3,
        }
        self._model = None
        self._feature_names: list[str] = []

    def train(self, X_train: pd.DataFrame, y_train: pd.Series) -> None:
        try:
            import xgboost as xgb
        except ImportError:
            raise ImportError("xgboost is required for XGBoostModel")

        self._feature_names = list(X_train.columns)
        dtrain = xgb.DMatrix(X_train, label=y_train)
        self._model = xgb.train(self._params, dtrain, num_boost_round=100)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("Model not trained")

        try:
            import xgboost as xgb
        except ImportError:
            raise ImportError("xgboost is required for XGBoostModel")

        dtest = xgb.DMatrix(X)
        return self._model.predict(dtest)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.argmax(self.predict_proba(X), axis=1)

    def save(self, path: Path) -> None:
        if self._model is None:
            raise RuntimeError("Model not trained")

        self._model.save_model(str(path))
        metadata = {
            "params": self._params,
            "feature_names": self._feature_names,
        }
        path.with_suffix(".json").write_text(json.dumps(metadata))

    def load(self, path: Path) -> None:
        try:
            import xgboost as xgb
        except ImportError:
            raise ImportError("xgboost is required for XGBoostModel")

        self._model = xgb.Booster()
        self._model.load_model(str(path))
        metadata = json.loads(path.with_suffix(".json").read_text())
        self._params = metadata["params"]
        self._feature_names = metadata["feature_names"]

    def get_feature_importance(self) -> dict[str, float]:
        if self._model is None:
            return {}
        importance = self._model.get_score(importance_type="gain")
        return {self._feature_names[int(k[1:])]: v for k, v in importance.items()}


class RandomForestModel:
    """Random Forest model wrapper for match outcome prediction."""

    def __init__(self, params: dict | None = None) -> None:
        self._params = params or {
            "n_estimators": 100,
            "max_depth": 10,
            "random_state": 42,
        }
        self._model = None
        self._feature_names: list[str] = []

    def train(self, X_train: pd.DataFrame, y_train: pd.Series) -> None:
        from sklearn.ensemble import RandomForestClassifier

        self._feature_names = list(X_train.columns)
        self._model = RandomForestClassifier(**self._params)
        self._model.fit(X_train, y_train)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("Model not trained")
        return self._model.predict_proba(X)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("Model not trained")
        return self._model.predict(X)

    def save(self, path: Path) -> None:
        import joblib
        joblib.dump(self._model, path)
        metadata = {"feature_names": self._feature_names}
        path.with_suffix(".json").write_text(json.dumps(metadata))

    def load(self, path: Path) -> None:
        import joblib
        self._model = joblib.load(path)
        metadata = json.loads(path.with_suffix(".json").read_text())
        self._feature_names = metadata["feature_names"]

    def get_feature_importance(self) -> dict[str, float]:
        if self._model is None:
            return {}
        return dict(zip(self._feature_names, self._model.feature_importances_))
