from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import mlflow
import numpy as np
import pandas as pd
import structlog
import yaml
from mlflow.tracking import MlflowClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sports_common.config import settings
from sports_common.logging import get_logger

logger = get_logger(__name__)


class ModelRegistry:
    """MLflow model registry for logging, versioning, and promotion."""

    def __init__(
        self,
        experiment_name: str = "sports-prediction",
        tracking_uri: str | None = None,
    ) -> None:
        self._tracking_uri = tracking_uri or settings.mlflow_tracking_uri
        mlflow.set_tracking_uri(self._tracking_uri)
        self._client = MlflowClient()
        self._experiment_name = experiment_name
        mlflow.set_experiment(experiment_name)

    def start_run(self, run_name: str | None = None) -> mlflow.ActiveRun:
        """Start an MLflow run."""
        run = mlflow.start_run(run_name=run_name)
        logger.info("mlflow_run_started", run_id=run.info.run_id, run_name=run_name)
        return run

    def log_params(self, params: dict[str, Any]) -> None:
        """Log parameters to current run."""
        mlflow.log_params(params)
        logger.debug("params_logged", params=list(params.keys()))

    def log_metrics(self, metrics: dict[str, float]) -> None:
        """Log metrics to current run."""
        mlflow.log_metrics(metrics)
        logger.debug("metrics_logged", metrics=list(metrics.keys()))

    def log_feature_manifest(self, features: list[str], version: str = "v1.0") -> None:
        """Log feature manifest for reproducibility."""
        manifest = {
            "version": version,
            "features": features,
            "feature_count": len(features),
        }
        manifest_json = json.dumps(manifest, indent=2)

        with mlflow.start_run():
            mlflow.log_dict(manifest, "feature_manifest.json")
        logger.info("feature_manifest_logged", feature_count=len(features))

    def log_model(
        self,
        model: Any,
        artifact_path: str = "model",
        registered_model_name: str | None = None,
    ) -> str:
        """Log a model to MLflow.

        Args:
            model: The model to log (sklearn, pytorch, etc.)
            artifact_path: Path to save the model artifact
            registered_model_name: Optional name for model registry

        Returns:
            Run ID of the logged model
        """
        with mlflow.start_run() as run:
            mlflow.sklearn.log_model(
                sk_model=model,
                artifact_path=artifact_path,
                registered_model_name=registered_model_name,
            )
            run_id = run.info.run_id
            logger.info(
                "model_logged",
                run_id=run_id,
                artifact_path=artifact_path,
                registered=registered_model_name is not None,
            )
        return run_id

    def log_pytorch_model(
        self,
        model: Any,
        artifact_path: str = "pytorch_model",
        registered_model_name: str | None = None,
    ) -> str:
        """Log a PyTorch model to MLflow."""
        with mlflow.start_run() as run:
            mlflow.pytorch.log_model(
                pytorch_model=model,
                artifact_path=artifact_path,
                registered_model_name=registered_model_name,
            )
            run_id = run.info.run_id
            logger.info("pytorch_model_logged", run_id=run_id)
        return run_id

    def log_xgboost_model(
        self,
        model: Any,
        artifact_path: str = "xgboost_model",
        registered_model_name: str | None = None,
    ) -> str:
        """Log an XGBoost model to MLflow."""
        with mlflow.start_run() as run:
            mlflow.xgboost.log_model(
                xgb_model=model,
                artifact_path=artifact_path,
                registered_model_name=registered_model_name,
            )
            run_id = run.info.run_id
            logger.info("xgboost_model_logged", run_id=run_id)
        return run_id

    def log_artifacts(self, local_dir: str, artifact_path: str | None = None) -> None:
        """Log additional artifacts (e.g., plots, configs)."""
        mlflow.log_artifacts(local_dir, artifact_path)
        logger.info("artifacts_logged", local_dir=local_dir, path=artifact_path)

    def get_latest_model_version(self, model_name: str, stage: str | None = None) -> int | None:
        """Get the latest version number of a registered model."""
        try:
            versions = self._client.get_latest_versions(model_name, stage=stage)
            if versions:
                return int(versions[0].version)
        except Exception as e:
            logger.warning("get_latest_version_failed", error=str(e))
        return None

    def promote_model(
        self,
        run_id: str,
        model_name: str,
        stage: str = "Staging",
    ) -> bool:
        """Promote a model to a specific stage in the registry.

        Args:
            run_id: MLflow run ID containing the model
            model_name: Name of the registered model
            stage: Target stage (Staging, Production, Archived)

        Returns:
            True if promotion successful
        """
        try:
            model_version = self._client.get_model_version_by_run(run_id, model_name)
            self._client.transition_model_version_stage(
                name=model_name,
                version=model_version.version,
                stage=stage,
            )
            logger.info(
                "model_promoted",
                model_name=model_name,
                version=model_version.version,
                stage=stage,
            )
            return True
        except Exception as e:
            logger.error("model_promotion_failed", error=str(e))
            return False

    def compare_models(
        self,
        model_names: list[str],
        metric: str = "val_brier_score",
    ) -> pd.DataFrame:
        """Compare multiple models by a specific metric."""
        comparisons = []

        for model_name in model_names:
            try:
                versions = self._client.get_latest_versions(model_name)
                if versions:
                    version = versions[0]
                    run = self._client.get_run(version.run_id)
                    metric_value = run.data.metrics.get(metric)

                    comparisons.append({
                        "model_name": model_name,
                        "version": version.version,
                        "stage": version.current_stage,
                        metric: metric_value,
                    })
            except Exception as e:
                logger.warning("model_comparison_failed", model=model_name, error=str(e))

        return pd.DataFrame(comparisons)

    def get_best_model(
        self,
        model_names: list[str],
        metric: str = "val_brier_score",
        lower_is_better: bool = True,
    ) -> str | None:
        """Get the best performing model based on a metric."""
        df = self.compare_models(model_names, metric)

        if df.empty:
            return None

        if lower_is_better:
            best_idx = df[metric].idxmin()
        else:
            best_idx = df[metric].idxmax()

        return df.loc[best_idx, "model_name"]

    def register_and_promote(
        self,
        model: Any,
        model_name: str,
        metrics: dict[str, float],
        params: dict[str, Any],
        features: list[str],
        promote_to: str = "Staging",
        compare_with: list[str] | None = None,
        brier_threshold: float = 0.20,
    ) -> tuple[str | None, bool]:
        """Complete workflow: register, log, and optionally promote.

        Args:
            model: Trained model
            model_name: Name for the registered model
            metrics: Evaluation metrics to log
            params: Hyperparameters to log
            features: Feature list for manifest
            promote_to: Stage to promote to (Staging, Production)
            compare_with: List of existing models to compare against
            brier_threshold: Maximum Brier score for promotion

        Returns:
            (run_id, was_promoted)
        """
        with mlflow.start_run() as run:
            self.log_params(params)
            self.log_metrics(metrics)

            try:
                mlflow.sklearn.log_model(
                    sk_model=model,
                    artifact_path="model",
                    registered_model_name=model_name,
                )
            except Exception:
                try:
                    mlflow.xgboost.log_model(
                        xgb_model=model,
                        artifact_path="model",
                        registered_model_name=model_name,
                    )
                except Exception:
                    mlflow.pytorch.log_model(
                        pytorch_model=model,
                        artifact_path="model",
                        registered_model_name=model_name,
                    )

            manifest = {
                "features": features,
                "feature_count": len(features),
            }
            mlflow.log_dict(manifest, "feature_manifest.json")

            run_id = run.info.run_id

        brier_score = metrics.get("val_brier_score", float("inf"))
        should_promote = brier_score <= brier_threshold

        if compare_with:
            best_existing = self.get_best_model(
                compare_with,
                metric="val_brier_score",
                lower_is_better=True,
            )
            if best_existing:
                best_df = self.compare_models([best_existing, model_name], "val_brier_score")
                current_brier = best_df[best_df["model_name"] == model_name]["val_brier_score"].values
                existing_brier = best_df[best_df["model_name"] == best_existing]["val_brier_score"].values

                if len(current_brier) > 0 and len(existing_brier) > 0:
                    should_promote = current_brier[0] < existing_brier[0]

        was_promoted = False
        if should_promote:
            was_promote = self.promote_model(run_id, model_name, promote_to)
            was_promoted = was_promote

        logger.info(
            "register_complete",
            run_id=run_id,
            model_name=model_name,
            brier_score=brier_score,
            promoted=was_promoted,
        )

        return run_id, was_promoted


def load_model_from_registry(
    model_name: str,
    stage: str = "Production",
) -> Any:
    """Load a model from the MLflow registry.

    Args:
        model_name: Name of the registered model
        stage: Stage to load from (Production, Staging, etc.)

    Returns:
        Loaded model
    """
    model_uri = f"models:/{model_name}/{stage}"
    model = mlflow.pyfunc.load_model(model_uri)
    logger.info("model_loaded", model_name=model_name, stage=stage)
    return model


def main() -> None:
    """Test registry functionality."""
    registry = ModelRegistry(experiment_name="sports-prediction-test")

    with registry.start_run(run_name="test-run"):
        registry.log_params({"n_estimators": 100, "max_depth": 6})
        registry.log_metrics({"accuracy": 0.65, "brier_score": 0.18})

    print("MLflow registry initialized successfully")


if __name__ == "__main__":
    main()
