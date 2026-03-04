import pytest
from datetime import datetime, timezone

from sports_common.utils.data_guard import (
    DataLeakageError,
    assert_feature_available_at_prediction_time,
    assert_no_look_ahead_bias,
    validate_chronological_split,
    get_leakage_test_description,
)


class TestDataGuard:
    def test_assert_feature_available_valid(self):
        feature_ts = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        pred_ts = datetime(2026, 3, 4, 12, 0, 0, tzinfo=timezone.utc)
        assert_feature_available_at_prediction_time(feature_ts, pred_ts, "test_feature")

    def test_assert_feature_available_invalid(self):
        feature_ts = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)
        pred_ts = datetime(2026, 3, 4, 12, 0, 0, tzinfo=timezone.utc)
        with pytest.raises(DataLeakageError):
            assert_feature_available_at_prediction_time(feature_ts, pred_ts, "test_feature")

    def test_assert_no_look_ahead_bias_valid(self):
        features = {"f1": 1.0, "f2": 2.0}
        pred_ts = datetime(2026, 3, 4, 12, 0, 0, tzinfo=timezone.utc)
        feature_timestamps = {
            "f1": datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc),
            "f2": datetime(2026, 3, 3, 12, 0, 0, tzinfo=timezone.utc),
        }
        assert_no_look_ahead_bias(features, pred_ts, feature_timestamps)

    def test_assert_no_look_ahead_bias_invalid(self):
        features = {"f1": 1.0}
        pred_ts = datetime(2026, 3, 4, 12, 0, 0, tzinfo=timezone.utc)
        feature_timestamps = {
            "f1": datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc),
        }
        with pytest.raises(DataLeakageError):
            assert_no_look_ahead_bias(features, pred_ts, feature_timestamps)

    def test_validate_chronological_split_valid(self):
        train_cutoff = datetime(2026, 3, 1, tzinfo=timezone.utc)
        val_start = datetime(2026, 3, 2, tzinfo=timezone.utc)
        test_start = datetime(2026, 3, 5, tzinfo=timezone.utc)
        validate_chronological_split(train_cutoff, val_start, test_start)

    def test_validate_chronological_split_train_val_overlap(self):
        train_cutoff = datetime(2026, 3, 5, tzinfo=timezone.utc)
        val_start = datetime(2026, 3, 2, tzinfo=timezone.utc)
        test_start = datetime(2026, 3, 10, tzinfo=timezone.utc)
        with pytest.raises(ValueError):
            validate_chronological_split(train_cutoff, val_start, test_start)

    def test_validate_chronological_split_val_test_overlap(self):
        train_cutoff = datetime(2026, 3, 1, tzinfo=timezone.utc)
        val_start = datetime(2026, 3, 5, tzinfo=timezone.utc)
        test_start = datetime(2026, 3, 5, tzinfo=timezone.utc)
        with pytest.raises(ValueError):
            validate_chronological_split(train_cutoff, val_start, test_start)

    def test_get_leakage_test_description_valid(self):
        feature_ts = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        pred_ts = datetime(2026, 3, 4, 12, 0, 0, tzinfo=timezone.utc)
        result = get_leakage_test_description("test_feature", pred_ts, feature_ts)
        assert "VALID" in result

    def test_get_leakage_test_description_invalid(self):
        feature_ts = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)
        pred_ts = datetime(2026, 3, 4, 12, 0, 0, tzinfo=timezone.utc)
        result = get_leakage_test_description("test_feature", pred_ts, feature_ts)
        assert "INVALID" in result
