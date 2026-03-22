from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import poisson
from scipy.optimize import minimize

from .base_model import BaseModel, ModelMeta


class PoissonModel(BaseModel):
    """Poisson regression for score-distribution modeling.

    Estimates expected goals (lambda) for each team and uses Monte Carlo
    simulation to derive match-outcome probabilities.
    """

    def __init__(self, meta: ModelMeta | None = None) -> None:
        if meta is None:
            meta = ModelMeta(
                name="poisson_match_outcome",
                version="1.0.0",
                hyperparameters={"simulations": 10000},
            )
        self.meta = meta
        self._attack: dict[str, float] = {}
        self._defense: dict[str, float] = {}
        self._home_advantage: float = 0.0
        self._simulations: int = meta.hyperparameters.get("simulations", 10000)
        self._teams: list[str] = []

    def train(self, X_train: pd.DataFrame, y_train: pd.Series) -> None:
        """Estimate attack/defense ratings via MLE."""
        teams = list(set(X_train["home_team"].tolist() + X_train["away_team"].tolist()))
        self._teams = teams
        n_teams = len(teams)
        team_idx = {t: i for i, t in enumerate(teams)}

        def neg_log_likelihood(params: np.ndarray) -> float:
            attacks = params[:n_teams]
            defenses = params[n_teams : 2 * n_teams]
            home_adv = params[-1]
            ll = 0.0
            for _, row in X_train.iterrows():
                hi = team_idx.get(row["home_team"])
                ai = team_idx.get(row["away_team"])
                if hi is None or ai is None:
                    continue
                lambda_home = np.exp(attacks[hi] + defenses[ai] + home_adv)
                lambda_away = np.exp(attacks[ai] + defenses[hi])
                home_score = row.get("home_score", 0)
                away_score = row.get("away_score", 0)
                ll += poisson.logpmf(int(home_score), lambda_home)
                ll += poisson.logpmf(int(away_score), lambda_away)
            return -ll

        x0 = np.zeros(2 * n_teams + 1)
        result = minimize(neg_log_likelihood, x0, method="L-BFGS-B")
        best = result.x

        self._attack = {t: best[i] for t, i in team_idx.items()}
        self._defense = {t: best[n_teams + i] for t, i in team_idx.items()}
        self._home_advantage = best[-1]

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Monte Carlo simulation of match outcomes."""
        probas = []

        for _, row in X.iterrows():
            lh = np.exp(
                self._attack.get(row["home_team"], 0)
                + self._defense.get(row["away_team"], 0)
                + self._home_advantage
            )
            la = np.exp(
                self._attack.get(row["away_team"], 0)
                + self._defense.get(row["home_team"], 0)
            )

            home_goals = np.random.poisson(lh, self._simulations)
            away_goals = np.random.poisson(la, self._simulations)

            home_win = np.mean(home_goals > away_goals)
            draw = np.mean(home_goals == away_goals)
            away_win = np.mean(home_goals < away_goals)

            probas.append([home_win, draw, away_win])

        return np.array(probas)

    def predict_score_distribution(
        self, X: pd.DataFrame, max_goals: int = 10
    ) -> list[dict[tuple[int, int], float]]:
        """Return score distribution probabilities."""
        distributions = []

        for _, row in X.iterrows():
            lh = np.exp(
                self._attack.get(row["home_team"], 0)
                + self._defense.get(row["away_team"], 0)
                + self._home_advantage
            )
            la = np.exp(
                self._attack.get(row["away_team"], 0)
                + self._defense.get(row["home_team"], 0)
            )

            dist = {}
            for h in range(max_goals + 1):
                for a in range(max_goals + 1):
                    prob = poisson.pmf(h, lh) * poisson.pmf(a, la)
                    dist[(h, a)] = prob
            distributions.append(dist)

        return distributions

    def get_attack_ratings(self) -> dict[str, float]:
        """Get team attack ratings."""
        return self._attack.copy()

    def get_defense_ratings(self) -> dict[str, float]:
        """Get team defense ratings."""
        return self._defense.copy()

    def get_home_advantage(self) -> float:
        """Get home advantage parameter."""
        return self._home_advantage

    def save(self, path: Path) -> None:
        data = {
            "attack": self._attack,
            "defense": self._defense,
            "home_advantage": self._home_advantage,
            "teams": self._teams,
            "simulations": self._simulations,
            "meta": {
                "name": self.meta.name,
                "version": self.meta.version,
                "hyperparameters": self.meta.hyperparameters,
            },
        }
        path.write_text(json.dumps(data))

    def load(self, path: Path) -> None:
        data = json.loads(path.read_text())
        self._attack = data["attack"]
        self._defense = data["defense"]
        self._home_advantage = data["home_advantage"]
        self._teams = data.get("teams", list(self._attack.keys()))
        self._simulations = data.get("simulations", 10000)
        self.meta = ModelMeta(
            name=data["meta"]["name"],
            version=data["meta"]["version"],
            hyperparameters=data["meta"]["hyperparameters"],
        )


def create_poisson_model(simulations: int = 10000) -> PoissonModel:
    """Factory function to create a Poisson model."""
    meta = ModelMeta(
        name="poisson_match_outcome",
        version="1.0.0",
        hyperparameters={"simulations": simulations},
    )
    return PoissonModel(meta)
