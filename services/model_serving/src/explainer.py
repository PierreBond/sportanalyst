from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import shap


class PredictionExplainer:
    """Generate SHAP explanations for model predictions.

    This class provides methods to compute and format SHAP values for
    model predictions, enabling interpretability of model decisions.
    """

    def __init__(
        self,
        model: Any,
        background_data: pd.DataFrame,
        feature_names: list[str] | None = None,
    ) -> None:
        """Initialize with a trained model and a background dataset for SHAP.

        Args:
            model: A trained model with a predict_proba method.
            background_data: A sample of 100-500 rows from the training set.
            feature_names: Optional list of feature names. If None, uses DataFrame columns.
        """
        self.model = model
        self.background_data = background_data
        self.feature_names = feature_names or list(background_data.columns)
        self._explainer: shap.Explainer | None = None
        self._background_cache: pd.DataFrame | None = None

        self._init_explainer()

    def _init_explainer(self) -> None:
        """Initialize the SHAP explainer."""
        try:
            self._explainer = shap.Explainer(
                self._predict_wrapper, self.background_data
            )
        except (TypeError, ValueError, AttributeError) as e:
            raise ValueError(f"Failed to initialize SHAP explainer: {e}") from e

    def _predict_wrapper(self, X: pd.DataFrame) -> np.ndarray:
        """Wrapper for model prediction compatible with SHAP.

        Args:
            X: Input data.

        Returns:
            Model predictions.
        """
        if isinstance(X, pd.DataFrame):
            return self.model.predict_proba(X)
        return self.model.predict_proba(pd.DataFrame(X, columns=self.feature_names))

    def explain(self, X: pd.DataFrame) -> list[dict[str, float]]:
        """Compute SHAP values for each prediction.

        Args:
            X: Input features for prediction(s). Shape: (n_samples, n_features).

        Returns:
            List of dicts mapping feature names to SHAP values,
            sorted by absolute impact (descending).
        """
        if self._explainer is None:
            raise RuntimeError("Explainer not initialized")

        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X, columns=self.feature_names)

        shap_values = self._explainer(X)
        results = []

        for i in range(len(X)):
            if len(shap_values.shape) == 3:
                feature_shap = {
                    col: round(float(shap_values.values[i, j, :].sum()), 6)
                    for j, col in enumerate(X.columns)
                }
            else:
                feature_shap = {
                    col: round(float(shap_values.values[i, j]), 6)
                    for j, col in enumerate(X.columns)
                }

            sorted_shap = dict(
                sorted(feature_shap.items(), key=lambda x: abs(x[1]), reverse=True)
            )
            results.append(sorted_shap)

        return results

    def explain_single(
        self, X: pd.DataFrame
    ) -> dict[str, float]:
        """Compute SHAP values for a single prediction.

        Args:
            X: Input features for a single prediction. Shape: (1, n_features).

        Returns:
            Dictionary mapping feature names to SHAP values,
            sorted by absolute impact (descending).
        """
        results = self.explain(X)
        return results[0]

    def get_top_features(
        self,
        X: pd.DataFrame,
        top_k: int = 10,
    ) -> list[tuple[str, float]]:
        """Get top-k features by SHAP absolute value.

        Args:
            X: Input features.
            top_k: Number of top features to return.

        Returns:
            List of (feature_name, shap_value) tuples.
        """
        shap_dict = self.explain_single(X)
        sorted_features = sorted(
            shap_dict.items(), key=lambda x: abs(x[1]), reverse=True
        )
        return sorted_features[:top_k]

    def format_explanation(
        self,
        X: pd.DataFrame,
        positive_label: str = "positive_drivers",
        negative_label: str = "negative_drivers",
    ) -> dict[str, Any]:
        """Format SHAP explanation for API response.

        Args:
            X: Input features for a single prediction.
            positive_label: Label for positive impact features.
            negative_label: Label for negative impact features.

        Returns:
            Formatted dictionary with positive and negative drivers.
        """
        shap_dict = self.explain_single(X)

        positive_drivers = []
        negative_drivers = []
        total_impact = sum(abs(v) for v in shap_dict.values())

        for feature, value in shap_dict.items():
            impact_pct = abs(value) / total_impact if total_impact > 0 else 0

            driver = {
                "feature": feature,
                "impact": round(value, 4),
                "impact_pct": round(impact_pct * 100, 1),
            }

            if value > 0:
                driver["label"] = self._generate_label(feature, value, True)
                positive_drivers.append(driver)
            else:
                driver["label"] = self._generate_label(feature, value, False)
                negative_drivers.append(driver)

        return {
            positive_label: positive_drivers[:10],
            negative_label: negative_drivers[:10],
        }

    def _generate_label(
        self,
        feature: str,
        impact: float,
        is_positive: bool,
    ) -> str:
        """Generate human-readable label for a feature impact.

        Args:
            feature: Feature name.
            impact: SHAP value.
            is_positive: Whether the impact is positive.

        Returns:
            Human-readable label.
        """
        impact_pct = abs(impact) * 100
        direction = "positive" if is_positive else "negative"

        feature_descriptions = {
            "momentum_xg_slope_5": "offensive form",
            "momentum_xg_slope_12": "long-term form",
            "rolling_avg_goals_5": "recent scoring",
            "rolling_avg_goals_10": "season scoring",
            "rolling_avg_xg_5": "expected goals",
            "is_home": "home advantage",
            "rest_days": "rest advantage",
            "team_avg_acwr": "workload ratio",
            "star_player_acwr": "key player fitness",
            "team_sentiment_twitter_24h": "fan sentiment",
            "cash_ticket_divergence": "sharp money",
            "line_movement_spread": "line movement",
        }

        description = feature_descriptions.get(feature, feature)
        return f"{description} ({direction}, {impact_pct:.1f}%)"

    def save_explainer(self, path: Path) -> None:
        """Save explainer configuration to disk.

        Args:
            path: Path to save the configuration.
        """
        state = {
            "feature_names": self.feature_names,
            "background_data_shape": self.background_data.shape,
        }
        path.write_text(json.dumps(state))

    def compute_shap_interaction_values(
        self, X: pd.DataFrame
    ) -> np.ndarray:
        """Compute SHAP interaction values between features.

        Args:
            X: Input features.

        Returns:
            SHAP interaction values array.
        """
        if self._explainer is None:
            raise RuntimeError("Explainer not initialized")

        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X, columns=self.feature_names)

        shap_values = self._explainer(X, interaction=True)
        return shap_values.values

    def get_feature_interactions(
        self,
        X: pd.DataFrame,
        feature: str,
        top_k: int = 5,
    ) -> list[tuple[str, float]]:
        """Get features with highest interaction values for a given feature.

        Args:
            X: Input features.
            feature: Feature to get interactions for.
            top_k: Number of top interactions to return.

        Returns:
            List of (feature_name, interaction_value) tuples.
        """
        interaction_values = self.compute_shap_interaction_values(X)

        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X, columns=self.feature_names)

        feature_idx = list(X.columns).index(feature)
        interactions = interaction_values[0, feature_idx, :]

        feature_interactions = [
            (col, round(float(interactions[i]), 6))
            for i, col in enumerate(X.columns)
            if i != feature_idx
        ]

        return sorted(feature_interactions, key=lambda x: abs(x[1]), reverse=True)[
            :top_k
        ]
