from __future__ import annotations

import json

import numpy as np
import pytest

from services.model_serving.src.predictor import ModelPredictor


def test_predictor_falls_back_to_placeholder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MODEL_URI", raising=False)
    monkeypatch.delenv("MODEL_PATH", raising=False)

    predictor = ModelPredictor()
    predictor.load_model()

    assert predictor.is_loaded is False

    probs = predictor.predict({"feature_a": 1.0})
    assert probs.shape == (3,)
    assert np.isclose(float(probs.sum()), 1.0)


def test_predictor_loads_local_xgboost_model(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    xgb = pytest.importorskip("xgboost")

    feature_names = ["f1", "f2", "f3"]
    X = np.array(
        [
            [0.1, 0.2, 0.3],
            [0.4, 0.1, 0.2],
            [0.7, 0.8, 0.9],
            [0.2, 0.9, 0.1],
            [0.8, 0.3, 0.2],
            [0.3, 0.6, 0.7],
        ],
        dtype=float,
    )
    y = np.array([0, 1, 2, 1, 2, 0], dtype=int)

    dtrain = xgb.DMatrix(X, label=y, feature_names=feature_names)
    booster = xgb.train(
        {
            "objective": "multi:softprob",
            "num_class": 3,
            "max_depth": 2,
            "eta": 0.3,
            "verbosity": 0,
        },
        dtrain,
        num_boost_round=6,
    )

    model_path = tmp_path / "xgboost_model.bin"
    booster.save_model(str(model_path))
    model_path.with_suffix(".json").write_text(
        json.dumps({"feature_names": feature_names}), encoding="utf-8"
    )

    monkeypatch.setenv("MODEL_PATH", str(model_path))
    monkeypatch.delenv("MODEL_URI", raising=False)

    predictor = ModelPredictor()
    predictor.load_model()

    assert predictor.is_loaded is True

    probs = predictor.predict({"f3": 0.5, "f1": 0.2, "f2": 0.8})
    assert probs.shape == (3,)
    assert np.all(probs >= 0.0)
    assert np.all(probs <= 1.0)
    assert np.isclose(float(probs.sum()), 1.0, atol=1e-5)
