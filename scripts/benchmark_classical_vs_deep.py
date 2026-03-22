#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "libs"))
sys.path.insert(0, str(PROJECT_ROOT / "services" / "model_training" / "src"))

from data_loader import DataLoader
from evaluator import ModelEvaluator
from models.gradient_boosting import create_random_forest_model, create_xgboost_model


def _evaluate_model(name: str, model, X_train, y_train, X_test, y_test) -> dict[str, float | str]:
    evaluator = ModelEvaluator()

    start = time.perf_counter()
    model.train(X_train, y_train)
    train_seconds = time.perf_counter() - start

    infer_start = time.perf_counter()
    y_prob = model.predict_proba(X_test)
    infer_seconds = time.perf_counter() - infer_start

    metrics = evaluator.compute_metrics(y_test, y_prob)
    metrics.update(
        {
            "model": name,
            "train_seconds": float(train_seconds),
            "infer_ms_per_sample": float((infer_seconds / max(len(X_test), 1)) * 1000.0),
        }
    )
    return metrics


def _markdown_table(rows: list[dict[str, float | str]]) -> str:
    headers = [
        "model",
        "accuracy",
        "f1_macro",
        "log_loss",
        "brier_score",
        "train_seconds",
        "infer_ms_per_sample",
    ]

    lines = ["| " + " | ".join(headers) + " |", "|---|---:|---:|---:|---:|---:|---:|"]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["model"]),
                    f"{float(row['accuracy']):.4f}",
                    f"{float(row['f1_macro']):.4f}",
                    f"{float(row['log_loss']):.4f}",
                    f"{float(row['brier_score']):.4f}",
                    f"{float(row['train_seconds']):.2f}",
                    f"{float(row['infer_ms_per_sample']):.3f}",
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def _load_training_data() -> tuple[pd.DataFrame, np.ndarray, pd.DataFrame, np.ndarray, str]:
    """Load data from DB-backed feature store, else fallback to synthetic data for CI/local runs."""
    loader = DataLoader()

    try:
        X_train, y_train, X_val, y_val, X_test, y_test = loader.prepare_training_data()
        if not X_train.empty and not X_test.empty and y_train is not None and y_test is not None:
            return X_train, y_train.astype(int).to_numpy(), X_test, y_test.astype(int).to_numpy(), "feature_store"
    except Exception:
        pass

    from sklearn.datasets import make_classification

    X, y = make_classification(
        n_samples=500,
        n_features=12,
        n_informative=10,
        n_redundant=2,
        n_classes=3,
        n_clusters_per_class=1,
        random_state=42,
    )
    cols = [f"f{i}" for i in range(12)]
    df = pd.DataFrame(X, columns=cols)

    split = int(len(df) * 0.8)
    X_train = df.iloc[:split].reset_index(drop=True)
    y_train = y[:split]
    X_test = df.iloc[split:].reset_index(drop=True)
    y_test = y[split:]
    return X_train, y_train, X_test, y_test, "synthetic"


def main() -> int:
    X_train, y_train, X_test, y_test, data_source = _load_training_data()

    rows: list[dict[str, float | str]] = []

    rows.append(
        _evaluate_model(
            "xgboost",
            create_xgboost_model(n_estimators=200, learning_rate=0.05, max_depth=6),
            X_train,
            y_train,
            X_test,
            y_test,
        )
    )

    rows.append(
        _evaluate_model(
            "random_forest",
            create_random_forest_model(n_estimators=300, max_depth=12),
            X_train,
            y_train,
            X_test,
            y_test,
        )
    )

    deep_status = "skipped: torch_not_installed"
    try:
        import torch  # noqa: F401
        from models.deep_learning import create_transformer_model

        rows.append(
            _evaluate_model(
                "transformer",
                create_transformer_model(n_heads=4),
                X_train,
                y_train,
                X_test,
                y_test,
            )
        )
        deep_status = "ran"
    except ImportError:
        pass
    except Exception as exc:
        deep_status = f"failed: {exc.__class__.__name__}"

    rows_sorted = sorted(rows, key=lambda x: float(x["accuracy"]), reverse=True)

    report_dir = PROJECT_ROOT / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"model_benchmark_{timestamp}.md"

    report = [
        "# Model Benchmark",
        "",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        f"Data source: {data_source}",
        f"Train samples: {len(X_train)}",
        f"Test samples: {len(X_test)}",
        f"Deep model status: {deep_status}",
        "",
        _markdown_table(rows_sorted),
        "",
        "Raw metrics JSON:",
        "```json",
        json.dumps(rows_sorted, indent=2),
        "```",
    ]

    report_path.write_text("\n".join(report), encoding="utf-8")

    print(f"Report written: {report_path}")
    print(_markdown_table(rows_sorted))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
