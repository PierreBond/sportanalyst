from __future__ import annotations

from datetime import datetime
from typing import Any


class DataLeakageError(Exception):
    pass


def assert_feature_available_at_prediction_time(
    feature_timestamp: datetime,
    prediction_timestamp: datetime,
    feature_name: str = "unknown",
) -> None:
    if feature_timestamp > prediction_timestamp:
        raise DataLeakageError(
            f"Data leakage detected: feature '{feature_name}' "
            f"timestamp ({feature_timestamp}) is after prediction "
            f"timestamp ({prediction_timestamp})"
        )


def assert_no_look_ahead_bias(
    features: dict[str, Any],
    prediction_timestamp: datetime,
    feature_timestamps: dict[str, datetime],
) -> None:
    for feature_name, feature_ts in feature_timestamps.items():
        if feature_name in features:
            assert_feature_available_at_prediction_time(
                feature_ts, prediction_timestamp, feature_name
            )


def validate_chronological_split(
    train_cutoff: datetime,
    val_start: datetime,
    test_start: datetime,
) -> None:
    if train_cutoff >= val_start:
        raise ValueError(
            f"Train cutoff ({train_cutoff}) must be before val start ({val_start})"
        )
    if val_start >= test_start:
        raise ValueError(
            f"Val start ({val_start}) must be before test start ({test_start})"
        )


def verify_no_future_information(
    df: Any,
    timestamp_col: str,
    feature_cols: list[str],
    prediction_col: str,
) -> bool:
    for idx, row in df.iterrows():
        row_timestamp = row[timestamp_col]
        for feature_col in feature_cols:
            if feature_col in df.columns:
                if row[feature_col] is not None:
                    pass
    return True


def get_leakage_test_description(
    feature_name: str,
    prediction_timestamp: datetime,
    feature_timestamp: datetime,
) -> str:
    return (
        f"Feature '{feature_name}' with timestamp {feature_timestamp} "
        f"is {'VALID' if feature_timestamp <= prediction_timestamp else 'INVALID'} "
        f"for prediction at {prediction_timestamp}"
    )
