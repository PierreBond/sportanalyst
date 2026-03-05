from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from models.injury_risk import InjuryRiskModel, compute_evaluation_metrics
from models.base_model import ModelMeta
from injury_risk_data_loader import InjuryRiskDataLoader
from registry import ModelRegistry


def load_config(config_path: str | Path) -> dict:
    """Load model configuration from YAML."""
    with open(config_path) as f:
        return yaml.safe_load(f)


def train_injury_risk_model(
    config: dict,
    data_loader: InjuryRiskDataLoader,
    registry: ModelRegistry,
) -> tuple[InjuryRiskModel, dict]:
    """Train injury risk model and return with metrics."""
    model_config = config.get("model", {})
    data_config = config.get("data", {})
    hyperparams = config.get("hyperparameters", {})

    start_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2025, 12, 31, tzinfo=timezone.utc)

    df = data_loader.load_training_data(start_date, end_date)

    train_df, val_df, test_df = data_loader.chronological_split(df)

    X_train = data_loader.prepare_features(train_df)
    y_train = train_df["target"]

    X_val = data_loader.prepare_features(val_df)
    y_val = val_df["target"]

    X_test = data_loader.prepare_features(test_df)
    y_test = test_df["target"]

    meta = ModelMeta(
        name=model_config.get("name", "injury_risk_xgboost"),
        version=model_config.get("version", "1.0.0"),
        hyperparameters=hyperparams,
    )

    model = InjuryRiskModel(meta=meta, **hyperparams)
    model.train(X_train, y_train)

    val_proba = model.predict_injury_probability(X_val)
    val_pred = (val_proba >= 0.5).astype(int)
    val_metrics = compute_evaluation_metrics(y_val.values, val_pred, val_proba)

    test_proba = model.predict_injury_probability(X_test)
    test_pred = (test_proba >= 0.5).astype(int)
    test_metrics = compute_evaluation_metrics(y_test.values, test_pred, test_proba)

    metrics = {}
    metrics.update({f"val_{k}": v for k, v in val_metrics.items()})
    metrics.update({f"test_{k}": v for k, v in test_metrics.items()})

    feature_importance = model.get_feature_importance()

    return model, metrics, feature_importance


def main():
    """Main training CLI for injury risk model."""
    parser = argparse.ArgumentParser(description="Injury Risk Model Training")
    parser.add_argument(
        "--config",
        type=str,
        help="Path to model config YAML file",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default="injury_risk",
        help="Model name for MLflow",
    )
    parser.add_argument(
        "--promote",
        action="store_true",
        help="Promote best model to Staging",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.85,
        help="F1 threshold for promotion",
    )

    args = parser.parse_args()

    if args.config:
        config = load_config(args.config)
    else:
        config = {
            "model": {
                "name": "injury_risk_xgboost",
                "version": "1.0.0",
            },
            "hyperparameters": {
                "n_estimators": 200,
                "max_depth": 5,
                "learning_rate": 0.05,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
            },
            "data": {},
        }

    data_loader = InjuryRiskDataLoader()
    registry = ModelRegistry(experiment_name="injury-risk")

    with registry.start_run(run_name=f"{args.model_name}_training"):
        registry.log_params(config.get("hyperparameters", {}))

        model, metrics, feature_importance = train_injury_risk_model(
            config,
            data_loader,
            registry,
        )

        registry.log_metrics(metrics)

        if feature_importance:
            registry.log_params({"feature_importance": feature_importance})

        try:
            registry.log_xgboost_model(
                model=model._model,
                artifact_path="injury_risk_model",
                registered_model_name=args.model_name,
            )
        except Exception as e:
            print(f"Warning: Could not log model to MLflow: {e}")

        print("\n=== Training Results ===")
        for metric, value in metrics.items():
            print(f"  {metric}: {value:.4f}" if isinstance(value, float) else f"  {metric}: {value}")

        print("\n=== Feature Importance ===")
        if feature_importance:
            sorted_features = sorted(
                feature_importance.items(),
                key=lambda x: x[1],
                reverse=True,
            )
            for feature, importance in sorted_features:
                print(f"  {feature}: {importance:.4f}")

    test_f1 = metrics.get("test_f1_macro", 0)
    if test_f1 >= args.threshold:
        print(f"\nModel meets F1 threshold ({test_f1:.3f} >= {args.threshold})")
    else:
        print(f"\nModel below F1 threshold ({test_f1:.3f} < {args.threshold})")

    if args.promote and test_f1 >= args.threshold:
        print("Promoting model to Staging...")
        print("(Requires MLflow model registry setup)")


if __name__ == "__main__":
    main()
