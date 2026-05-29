from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


class ModelPredictor:
    """Loads an ML model and runs inference for match outcome predictions.

    Supports MLflow URI loading and local artifact loading.
    Falls back to a placeholder distribution when no model is available.
    """

    def __init__(self) -> None:
        self._model: Any = None
        self._model_name: str = "xgboost_match_outcome"
        self._model_version: str = "v2.1"
        self._is_loaded: bool = False
        self._model_uri: str | None = os.getenv("MODEL_URI")
        self._model_path: str | None = os.getenv("MODEL_PATH")
        self._feature_names: list[str] = []

    @property
    def is_loaded(self) -> bool:
        """Whether a model has been successfully loaded."""
        return self._is_loaded

    @property
    def model_name(self) -> str:
        """Name of the loaded model."""
        return self._model_name

    @property
    def model_version(self) -> str:
        """Version of the loaded model."""
        return self._model_version

    def load_model(self, model_name: str | None = None) -> None:
        """Load a model from MLflow registry.

        Args:
            model_name: Optional model name override.

        Resolution order:
        1) MODEL_URI (mlflow.pyfunc)
        2) MODEL_PATH (joblib or XGBoost booster)
        3) Placeholder fallback
        """
        if model_name:
            self._model_name = model_name

        try:
            if self._model_uri:
                import mlflow

                self._model = mlflow.pyfunc.load_model(self._model_uri)
                self._is_loaded = True
                self._model_version = os.getenv("MODEL_VERSION", "mlflow")
                logger.info(
                    "model_loaded_from_mlflow",
                    model_name=self._model_name,
                    model_uri=self._model_uri,
                )
                return

            if self._model_path:
                # Try multiple path resolution strategies
                predictor_dir = Path(__file__).resolve().parent
                workspace_root = predictor_dir.parent.parent.parent  # src -> model_serving -> services -> workspace
                
                candidates = [
                    Path(self._model_path),
                    Path(self._model_path).resolve(),
                    workspace_root / self._model_path,
                    predictor_dir.parent / self._model_path,  # models/ relative to src/
                ]
                
                model_path = None
                for candidate in candidates:
                    if candidate.exists():
                        model_path = candidate
                        logger.info(
                            "model_path_resolved",
                            candidate=str(model_path),
                        )
                        break
                
                if not model_path:
                    logger.warning(
                        "model_path_not_found",
                        model_path=self._model_path,
                        candidates=[str(c) for c in candidates],
                    )

                if model_path:
                    logger.debug(
                        "attempting_model_load",
                        model_path=str(model_path),
                    )

                    try:
                        import joblib

                        self._model = joblib.load(model_path)
                        self._is_loaded = True
                        self._model_version = os.getenv("MODEL_VERSION", "local-artifact")
                        logger.info(
                            "model_loaded_from_joblib",
                            model_name=self._model_name,
                            model_path=str(model_path),
                        )
                        return
                    except Exception as je:
                        logger.debug(
                            "joblib_load_failed",
                            model_name=self._model_name,
                            error=str(je),
                        )

                    try:
                        import xgboost as xgb
                        import json

                        booster = xgb.Booster()
                        booster.load_model(str(model_path))
                        
                        # Load metadata if available
                        metadata_path = model_path.with_suffix(".json")
                        if metadata_path.exists():
                            metadata = json.loads(metadata_path.read_text())
                            self._feature_names = metadata.get("feature_names", [])
                        
                        self._model = booster
                        self._is_loaded = True
                        self._model_version = os.getenv("MODEL_VERSION", "local-xgboost")
                        logger.info(
                            "model_loaded_from_xgboost",
                            model_name=self._model_name,
                            model_path=str(model_path),
                        )
                        return
                    except Exception as e:
                        logger.debug(
                            "xgboost_load_failed",
                            model_name=self._model_name,
                            model_path=str(model_path),
                            error=str(e),
                        )
                        pass

                    logger.warning(
                        "model_load_local_failed",
                        model_name=self._model_name,
                        model_path=str(model_path),
                    )
                else:
                    logger.warning(
                        "model_path_not_resolved",
                        model_path=self._model_path,
                    )

            self._model = None
            self._is_loaded = False
            logger.warning(
                "model_load_placeholder",
                model_name=self._model_name,
                detail="Set MODEL_URI or MODEL_PATH to enable real model loading",
            )
        except Exception as e:
            logger.error("model_load_failed", model_name=self._model_name, error=str(e))
            raise

    def predict(self, features: dict[str, Any]) -> np.ndarray:
        """Run inference on a feature dict and return class probabilities.

        Args:
            features: Dictionary of feature_name -> value.

        Returns:
            Array of [home_win_prob, draw_prob, away_win_prob].
        """
        if self._model is not None and self._is_loaded:
            import pandas as pd

            feature_df = pd.DataFrame([features])

            if hasattr(self._model, "predict_proba"):
                raw_probs = self._model.predict_proba(feature_df)
            elif hasattr(self._model, "predict"):
                try:
                    import xgboost as xgb

                    if isinstance(self._model, xgb.Booster):
                        # Keep feature ordering stable for booster-based inference.
                        if self._feature_names:
                            ordered_features = {
                                name: features.get(name, 0.0) for name in self._feature_names
                            }
                            feature_df = pd.DataFrame([ordered_features])
                        raw_probs = self._model.predict(
                            xgb.DMatrix(feature_df, feature_names=list(feature_df.columns))
                        )
                    else:
                        raw_probs = self._model.predict(feature_df)
                except Exception:
                    raw_probs = self._model.predict(feature_df)
            else:
                raw_probs = None

            if raw_probs is not None:
                probs = np.asarray(raw_probs)
                if probs.ndim == 1:
                    return probs
                if probs.ndim >= 2:
                    return probs[0]

        # Placeholder probabilities until real model is loaded
        logger.debug("predict_placeholder", detail="Using placeholder probabilities")
        return np.array([0.45, 0.25, 0.30])
