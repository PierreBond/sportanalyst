from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize

from .base_model import BaseModel, ModelMeta


@dataclass
class BayesianMatchResult:
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    home_goals_expected: float
    away_goals_expected: float


class BayesianTeamModel(BaseModel):
    """Bayesian inference model for team skill estimation.

    Uses a hierarchical Bayesian model to estimate team attack and defense
    strengths, then derives match outcome probabilities.
    """

    def __init__(self, meta: ModelMeta) -> None:
        self.meta = meta
        self._team_attack: dict[str, float] = {}
        self._team_defense: dict[str, float] = {}
        self._home_advantage: float = 0.0
        self._league_strength: float = 0.0
        self._prior_strength: float = 0.0
        self._simulations: int = meta.hyperparameters.get("simulations", 10000)
        self._model = None

    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
    ) -> None:
        """Train Bayesian model using MCMC-style optimization.

        Args:
            X_train: Features DataFrame with team identifiers
            y_train: Target (not used directly - we extract scores from X_train)
        """
        teams = list(set(
            X_train.get("home_team", []).tolist() +
            X_train.get("away_team", []).tolist()
        ))

        if not teams:
            teams = [f"Team_{i}" for i in range(20)]

        team_idx = {t: i for i, t in enumerate(teams)}
        n_teams = len(teams)

        home_scores = X_train.get("home_score", pd.Series([2] * len(X_train))).values
        away_scores = X_train.get("away_score", pd.Series([1] * len(X_train))).values

        home_teams = X_train.get("home_team", pd.Series(teams[:len(X_train)])).values
        away_teams = X_train.get("away_team", pd.Series(teams[len(X_train):] + teams[:len(X_train)])).values

        if len(home_teams) < len(home_scores):
            home_teams = np.tile(home_teams, (len(home_scores) // len(home_teams) + 1))[:len(home_scores)]
        if len(away_teams) < len(away_scores):
            away_teams = np.tile(away_teams, (len(away_scores) // len(away_teams) + 1))[:len(away_scores)]

        def neg_log_likelihood(params: np.ndarray) -> float:
            attack = params[:n_teams]
            defense = params[n_teams:2 * n_teams]
            home_adv = params[2 * n_teams]
            league_strength = params[2 * n_teams + 1]

            ll = 0.0
            for i in range(len(home_scores)):
                try:
                    hi = team_idx.get(home_teams[i], 0)
                    ai = team_idx.get(away_teams[i], 0)

                    lambda_home = np.exp(attack[hi] + defense[ai] + home_adv + league_strength)
                    lambda_away = np.exp(attack[ai] + defense[hi] + league_strength)

                    lambda_home = max(0.1, min(lambda_home, 10))
                    lambda_away = max(0.1, min(lambda_away, 10))

                    ll += stats.poisson.logpmf(int(home_scores[i]), lambda_home)
                    ll += stats.poisson.logpmf(int(away_scores[i]), lambda_away)
                except (KeyError, IndexError):
                    continue

            prior = 0.0
            for att in attack[:min(5, len(attack))]:
                prior += stats.norm.logpdf(att, 0, 1)
            for def_ in defense[:min(5, len(defense))]:
                prior += stats.norm.logpdf(def_, 0, 1)

            return -(ll + prior)

        x0 = np.zeros(2 * n_teams + 2)

        result = minimize(
            neg_log_likelihood,
            x0,
            method="L-BFGS-B",
            options={"maxiter": 500},
        )

        best = result.x
        for i, team in enumerate(teams):
            if i < n_teams:
                self._team_attack[team] = best[i]
                self._team_defense[team] = best[n_teams + i]

        self._home_advantage = best[2 * n_teams] if 2 * n_teams < len(best) else 0.3
        self._league_strength = best[2 * n_teams + 1] if 2 * n_teams + 1 < len(best) else 0.0
        self._prior_strength = 0.0

        logger.info(
            "bayesian_model_trained",
            n_teams=n_teams,
            home_advantage=self._home_advantage,
        )

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict match outcome probabilities using Monte Carlo simulation.

        Args:
            X: DataFrame with 'home_team' and 'away_team' columns

        Returns:
            Array of shape (n_samples, 3) with [home_win, draw, away_win] probabilities
        """
        probas = []

        for _, row in X.iterrows():
            home_team = row.get("home_team", "Team_0")
            away_team = row.get("away_team", "Team_1")

            attack_home = self._team_attack.get(home_team, 0)
            attack_away = self._team_attack.get(away_team, 0)
            def_home = self._team_defense.get(home_team, 0)
            def_away = self._team_defense.get(away_team, 0)

            lambda_home = np.exp(
                attack_home + def_away + self._home_advantage + self._league_strength
            )
            lambda_away = np.exp(
                attack_away + def_home + self._league_strength
            )

            lambda_home = max(0.1, min(lambda_home, 10))
            lambda_away = max(0.1, min(lambda_away, 10))

            home_goals = np.random.poisson(lambda_home, self._simulations)
            away_goals = np.random.poisson(lambda_away, self._simulations)

            home_win = np.mean(home_goals > away_goals)
            draw = np.mean(home_goals == away_goals)
            away_win = np.mean(home_goals < away_goals)

            total = home_win + draw + away_win
            if total > 0:
                home_win /= total
                draw /= total
                away_win /= total

            probas.append([home_win, draw, away_win])

        return np.array(probas)

    def predict_scores(
        self,
        X: pd.DataFrame,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Predict expected goals for home and away teams.

        Args:
            X: DataFrame with team identifiers

        Returns:
            Tuple of (home_expected, away_expected) arrays
        """
        home_expected = []
        away_expected = []

        for _, row in X.iterrows():
            home_team = row.get("home_team", "Team_0")
            away_team = row.get("away_team", "Team_1")

            attack_home = self._team_attack.get(home_team, 0)
            attack_away = self._team_attack.get(away_team, 0)
            def_home = self._team_defense.get(home_team, 0)
            def_away = self._team_defense.get(away_team, 0)

            lambda_home = np.exp(
                attack_home + def_away + self._home_advantage + self._league_strength
            )
            lambda_away = np.exp(
                attack_away + def_home + self._league_strength
            )

            home_expected.append(lambda_home)
            away_expected.append(lambda_away)

        return np.array(home_expected), np.array(away_expected)

    def get_team_rating(self, team: str) -> dict[str, float]:
        """Get attack and defense ratings for a team."""
        return {
            "attack": self._team_attack.get(team, 0),
            "defense": self._team_defense.get(team, 0),
        }

    def get_feature_importance(self) -> dict[str, float] | None:
        """Return team skill parameters as pseudo feature importance."""
        if not self._team_attack:
            return None

        all_ratings = list(self._team_attack.values()) + list(self._team_defense.values())

        return {
            "home_advantage": float(self._home_advantage),
            "league_strength": float(self._league_strength),
            "n_teams": float(len(self._team_attack)),
            "avg_attack": float(np.mean(list(self._team_attack.values()))) if self._team_attack else 0,
            "avg_defense": float(np.mean(list(self._team_defense.values()))) if self._team_defense else 0,
        }

    def save(self, path: Path) -> None:
        """Save model to disk."""
        import json

        data = {
            "team_attack": self._team_attack,
            "team_defense": self._team_defense,
            "home_advantage": self._home_advantage,
            "league_strength": self._league_strength,
            "prior_strength": self._prior_strength,
            "simulations": self._simulations,
        }

        path.write_text(json.dumps(data))

    def load(self, path: Path) -> None:
        """Load model from disk."""
        import json

        data = json.loads(path.read_text())

        self._team_attack = data["team_attack"]
        self._team_defense = data["team_defense"]
        self._home_advantage = data["home_advantage"]
        self._league_strength = data["league_strength"]
        self._prior_strength = data.get("prior_strength", 0)
        self._simulations = data.get("simulations", 10000)


def create_bayesian_model(
    n_estimators: int = 100,
    simulations: int = 10000,
) -> BayesianTeamModel:
    """Factory function to create a Bayesian model."""
    meta = ModelMeta(
        name="bayesian_team_model",
        version="1.0",
        hyperparameters={
            "n_estimators": n_estimators,
            "simulations": simulations,
        },
    )
    return BayesianTeamModel(meta)
