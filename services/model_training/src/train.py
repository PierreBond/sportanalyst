from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_loader import DataLoader
from models.base_model import ModelMeta
from models.poisson import create_poisson_model
from models.bayesian import create_bayesian_model
from models.gradient_boosting import create_xgboost_model, create_random_forest_model
from evaluator import ModelEvaluator
from registry import ModelRegistry
from sports_common.logging import setup_logging, get_logger

try:
    from models.deep_learning import (
        create_cnn_model,
        create_lstm_model,
        create_cnn_lstm_model,
        create_transformer_model,
        create_tabnet_model,
    )
except ImportError:
    create_cnn_model = None
    create_lstm_model = None
    create_cnn_lstm_model = None
    create_transformer_model = None
    create_tabnet_model = None

setup_logging("model-training")
logger = get_logger(__name__)


MODEL_FACTORIES = {
    "poisson": create_poisson_model,
    "bayesian": create_bayesian_model,
    "random_forest": create_random_forest_model,
    "xgboost": create_xgboost_model,
}

if create_cnn_model is not None:
    MODEL_FACTORIES.update(
        {
            "cnn": create_cnn_model,
            "lstm": create_lstm_model,
            "cnn_lstm": create_cnn_lstm_model,
            "transformer": create_transformer_model,
            "tabnet": create_tabnet_model,
        }
    )


def load_config(config_path: str | Path) -> dict[str, Any]:
    """Load model configuration from YAML."""
    with open(config_path) as f:
        return yaml.safe_load(f)


def train_model(
    model_name: str,
    config: dict[str, Any],
    data_loader: DataLoader,
    registry: ModelRegistry,
) -> dict[str, float]:
    """Train a single model and return metrics."""
    logger.info("training_model", model=model_name)

    model_config = config.get("model", {})
    data_config = config.get("data", {})
    hyperparams = config.get("hyperparameters", {})

    leagues = data_config.get("leagues")
    seasons = data_config.get("train_seasons")
    val_season = data_config.get("val_season")
    test_season = data_config.get("test_season")

    X_train, y_train, X_val, y_val, X_test, y_test = data_loader.prepare_training_data(
        leagues=leagues,
        seasons=seasons,
        train_seasons=seasons,
        val_season=val_season,
        test_season=test_season,
    )

    if X_train.empty:
        logger.warning("no_training_data", model=model_name)
        return {}

    factory = MODEL_FACTORIES.get(model_name)
    if not factory:
        raise ValueError(f"Unknown model: {model_name}")

    model = factory(**hyperparams)

    model.train(X_train, y_train)

    val_predictions = model.predict_proba(X_val) if not X_val.empty else None
    test_predictions = model.predict_proba(X_test) if not X_test.empty else None

    evaluator = ModelEvaluator()

    metrics = {}

    if val_predictions is not None and y_val is not None:
        val_metrics = evaluator.compute_metrics(
            y_val,
            val_predictions,
            model_name=model_name,
        )
        metrics.update({f"val_{k}": v for k, v in val_metrics.items()})

    if test_predictions is not None and y_test is not None:
        test_metrics = evaluator.compute_metrics(
            y_test,
            test_predictions,
            model_name=model_name,
        )
        metrics.update({f"test_{k}": v for k, v in test_metrics.items()})

    feature_names = data_loader.get_feature_names(X_train)

    with registry.start_run(run_name=f"{model_name}_training"):
        registry.log_params(hyperparams)
        registry.log_metrics(metrics)

        try:
            registry.log_model(model, artifact_path="model", registered_model_name=model_name)
        except Exception as e:
            logger.warning("model_log_failed", error=str(e))

    logger.info("model_trained", model=model_name, metrics=metrics)

    return metrics


def train_all_models(config_dir: Path) -> dict[str, dict[str, float]]:
    """Train all models from config directory."""
    data_loader = DataLoader()
    registry = ModelRegistry()

    results = {}

    config_files = list(config_dir.glob("*.yaml"))

    for config_file in config_files:
        model_name = config_file.stem
        config = load_config(config_file)

        try:
            metrics = train_model(model_name, config, data_loader, registry)
            results[model_name] = metrics
        except Exception as e:
            logger.error("training_failed", model=model_name, error=str(e))
            results[model_name] = {"error": str(e)}

    return results


def compare_and_promote(
    results: dict[str, dict[str, float]],
    registry: ModelRegistry,
    threshold: float = 0.20,
) -> None:
    """Compare models and promote the best one."""
    valid_models = {
        name: metrics for name, metrics in results.items() if "val_brier_score" in metrics
    }

    if not valid_models:
        logger.warning("no_valid_models")
        return

    best_model = min(
        valid_models.items(),
        key=lambda x: x[1].get("val_brier_score", float("inf")),
    )

    model_name, metrics = best_model

    if metrics.get("val_brier_score", float("inf")) <= threshold:
        logger.info(
            "promoting_model",
            model=model_name,
            brier_score=metrics["val_brier_score"],
        )
    else:
        logger.warning(
            "model_below_threshold",
            model=model_name,
            brier_score=metrics.get("val_brier_score"),
            threshold=threshold,
        )


def main() -> None:
    """Main training CLI."""
    parser = argparse.ArgumentParser(description="Model Training CLI")
    parser.add_argument(
        "--config",
        type=str,
        help="Path to model config YAML file",
    )
    parser.add_argument(
        "--config-dir",
        type=str,
        default="configs",
        help="Directory containing model configs (for training all)",
    )
    parser.add_argument(
        "--model",
        type=str,
        choices=list(MODEL_FACTORIES.keys()),
        help="Specific model to train",
    )
    parser.add_argument(
        "--promote",
        action="store_true",
        help="Promote best model to Production",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.20,
        help="Brier score threshold for promotion",
    )

    args = parser.parse_args()

    base_path = Path(__file__).parent

    if args.config:
        config = load_config(args.config)
        model_name = Path(args.config).stem

        data_loader = DataLoader()
        registry = ModelRegistry()

        metrics = train_model(model_name, config, data_loader, registry)
        logger.info("training_complete", model=model_name, metrics=metrics)

    elif args.model:
        config = {
            "model": {"name": args.model},
            "hyperparameters": {},
            "data": {},
        }

        data_loader = DataLoader()
        registry = ModelRegistry()

        metrics = train_model(args.model, config, data_loader, registry)
        logger.info("training_complete", model=args.model, metrics=metrics)

    else:
        config_dir = base_path / args.config_dir

        if not config_dir.exists():
            logger.error("config_directory_not_found", path=str(config_dir))
            sys.exit(1)

        results = train_all_models(config_dir)

        for model_name, metrics in results.items():
            logger.info("model_results", model=model_name, metrics=metrics)

        if args.promote:
            registry = ModelRegistry()
            compare_and_promote(results, registry, args.threshold)


if __name__ == "__main__":
    main()
