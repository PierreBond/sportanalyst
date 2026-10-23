from __future__ import annotations

import numpy as np
import pytest

from services.model_serving.src.betting import (
    BettingEngine,
    BetSelection,
    cap_slate,
    implied_probability,
    kelly_fraction,
    remove_vig,
)
from services.model_serving.src.calibrator import ProbabilityCalibrator


class TestCapSlate:
    """Tests for cap_slate."""

    @staticmethod
    def _bet(edge: float, stake: float):
        return {"edge": edge, "stake_pct": stake}

    def test_keeps_highest_edges_first(self) -> None:
        bets = [self._bet(0.03 + i * 0.01, 0.01) for i in range(12)]
        kept = cap_slate(bets, max_bets=5)
        assert len(kept) == 5
        edges = [b["edge"] for b in kept]
        assert edges == sorted(edges, reverse=True)

    def test_respects_max_bets(self) -> None:
        bets = [self._bet(0.05, 0.01) for _ in range(15)]
        assert len(cap_slate(bets, max_bets=10)) == 10

    def test_respects_daily_exposure(self) -> None:
        bets = [self._bet(0.05, 0.06) for _ in range(10)]
        kept = cap_slate(bets, max_daily_exposure=0.15)
        assert sum(b["stake_pct"] for b in kept) <= 0.15

    def test_small_stake_fills_budget(self) -> None:
        bets = [self._bet(0.10, 0.12), self._bet(0.03, 0.01)]
        kept = cap_slate(bets, max_daily_exposure=0.15)
        assert len(kept) == 2

    def test_empty(self) -> None:
        assert cap_slate([]) == []


class TestImpliedProbability:
    """Tests for implied_probability."""

    def test_even_odds(self) -> None:
        assert implied_probability(2.0) == 0.5

    def test_heavy_favourite(self) -> None:
        result = implied_probability(1.25)
        assert 0.79 < result < 0.81

    def test_invalid_odds_raises(self) -> None:
        with pytest.raises(ValueError):
            implied_probability(1.0)
        with pytest.raises(ValueError):
            implied_probability(0.5)


class TestKellyFraction:
    """Tests for kelly_fraction."""

    def test_positive_edge(self) -> None:
        stake = kelly_fraction(0.6, 2.5, fraction=1.0)
        assert stake > 0.0

    def test_no_edge_returns_zero(self) -> None:
        stake = kelly_fraction(0.3, 2.0, fraction=1.0)
        assert stake == 0.0

    def test_invalid_odds_returns_zero(self) -> None:
        assert kelly_fraction(0.5, 1.0) == 0.0


class TestRemoveVig:
    """Tests for remove_vig."""

    def test_probabilities_sum_to_one(self) -> None:
        h, a, d = remove_vig(2.0, 3.5, 3.0)
        assert abs(h + a + d - 1.0) < 0.001

    def test_two_way_market(self) -> None:
        h, a, d = remove_vig(1.9, 1.9)
        assert d is None
        assert abs(h + a - 1.0) < 0.001


class TestBettingEngine:
    """Tests for BettingEngine."""

    def test_detect_value_bet_with_edge(self) -> None:
        engine = BettingEngine(edge_threshold=0.03)
        bet = engine.detect_value_bet(
            match_id="m1",
            selection=BetSelection.HOME_WIN,
            model_prob=0.60,
            decimal_odds=2.0,
            sportsbook="test_book",
        )
        assert bet is not None
        assert bet.match_id == "m1"
        assert bet.selection == "home_win"

    def test_no_value_bet_when_no_edge(self) -> None:
        engine = BettingEngine(edge_threshold=0.03)
        bet = engine.detect_value_bet(
            match_id="m1",
            selection=BetSelection.HOME_WIN,
            model_prob=0.48,
            decimal_odds=2.0,
            sportsbook="test_book",
        )
        assert bet is None

    def test_evaluate_bets_finds_value(self) -> None:
        engine = BettingEngine(edge_threshold=0.03)
        bets = engine.evaluate_bets(
            match_id="m1",
            probabilities={"home_win": 0.65, "draw": 0.20, "away_win": 0.15},
            odds={"home_win": 1.80, "draw": 3.50, "away_win": 5.00},
            sportsbook="test_book",
        )
        assert isinstance(bets, list)

    def test_clv_calculation(self) -> None:
        engine = BettingEngine()
        clv = engine.calculate_closing_line_value(0.55, 2.0)
        assert clv == pytest.approx(0.05, abs=0.01)


class TestProbabilityCalibrator:
    """Tests for ProbabilityCalibrator."""

    def test_fit_and_calibrate(self) -> None:
        rng = np.random.RandomState(42)
        n = 100
        raw_probs = rng.dirichlet([1, 1, 1], n)
        y_true = rng.choice(3, n)

        calibrator = ProbabilityCalibrator()
        calibrator.fit(raw_probs, y_true)
        calibrated = calibrator.calibrate(raw_probs)

        assert calibrated.shape == raw_probs.shape
        np.testing.assert_allclose(calibrated.sum(axis=1), 1.0, atol=1e-6)

    def test_calibrate_before_fit_raises(self) -> None:
        calibrator = ProbabilityCalibrator()
        with pytest.raises(RuntimeError):
            calibrator.calibrate(np.array([[0.5, 0.3, 0.2]]))

    def test_insufficient_data_raises(self) -> None:
        calibrator = ProbabilityCalibrator()
        with pytest.raises(ValueError):
            calibrator.fit(
                np.array([[0.5, 0.3, 0.2]]),
                np.array([0]),
            )
