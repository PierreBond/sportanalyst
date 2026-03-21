import pytest

from sports_common.utils.math import (
    poisson_pmf,
    poisson_cdf,
    kelly_fraction,
    fractional_kelly,
    implied_probability,
    remove_vigorish,
    brier_score,
    brier_score_multiclass,
    log_loss,
    expected_value,
    closing_line_value,
    calculate_roi,
)


class TestPoisson:
    def test_poisson_pmf_basic(self):
        result = poisson_pmf(3, 2.5)
        assert result > 0
        assert result < 1

    def test_poisson_pmf_zero(self):
        result = poisson_pmf(0, 2.5)
        assert result > 0

    def test_poisson_pmf_invalid_params(self):
        with pytest.raises(ValueError):
            poisson_pmf(-1, 2.5)
        with pytest.raises(ValueError):
            poisson_pmf(3, 0)

    def test_poisson_cdf(self):
        result = poisson_cdf(3, 2.5)
        assert result > 0
        assert result <= 1


class TestKelly:
    def test_kelly_fraction_positive_edge(self):
        result = kelly_fraction(2.5, 0.6)
        assert result > 0

    def test_kelly_fraction_negative_edge(self):
        result = kelly_fraction(2.0, 0.3)
        assert result == 0.0

    def test_kelly_fraction_full_kelly(self):
        result = kelly_fraction(2.0, 0.6)
        assert 0 < result <= 1

    def test_fractional_kelly(self):
        full = kelly_fraction(2.0, 0.6)
        frac = fractional_kelly(2.0, 0.6, 0.5)
        assert frac == pytest.approx(full * 0.5)


class TestImpliedProbability:
    def test_implied_probability_basic(self):
        result = implied_probability(2.0)
        assert result == 0.5

    def test_implied_probability_with_vigorish(self):
        result = implied_probability(2.0, vigorish=0.05)
        assert result > 0

    def test_implied_probability_invalid(self):
        with pytest.raises(ValueError):
            implied_probability(0)
        with pytest.raises(ValueError):
            implied_probability(-1)


class TestRemoveVigorish:
    def test_remove_vigorish_two_outcome(self):
        home, away, draw = remove_vigorish(2.0, 2.0)
        assert abs((home + away) - 1.0) < 0.01

    def test_remove_vigorish_three_outcome(self):
        home, away, draw = remove_vigorish(3.0, 3.0, 3.0)
        assert draw is not None
        assert abs((home + away + draw) - 1.0) < 0.01


class TestBrierScore:
    def test_brier_score_perfect(self):
        predictions = [1.0, 0.0, 1.0]
        outcomes = [1, 0, 1]
        result = brier_score(predictions, outcomes)
        assert result == 0.0

    def test_brier_score_worst(self):
        predictions = [0.0, 1.0, 0.0]
        outcomes = [1, 0, 1]
        result = brier_score(predictions, outcomes)
        assert result == 1.0

    def test_brier_score_mismatch_length(self):
        with pytest.raises(ValueError):
            brier_score([1.0], [1, 0])


class TestBrierScoreMulticlass:
    def test_brier_multiclass_perfect(self):
        predictions = [
            {"home": 1.0, "away": 0.0, "draw": 0.0},
            {"home": 0.0, "away": 1.0, "draw": 0.0},
        ]
        outcomes = ["home", "away"]
        result = brier_score_multiclass(predictions, outcomes, ["home", "away", "draw"])
        assert result == 0.0


class TestLogLoss:
    def test_log_loss_perfect(self):
        predictions = [1.0, 0.0]
        outcomes = [1, 0]
        result = log_loss(predictions, outcomes)
        assert result == pytest.approx(0.0)

    def test_log_loss_mismatch_length(self):
        with pytest.raises(ValueError):
            log_loss([1.0], [1, 0])


class TestExpectedValue:
    def test_expected_value_positive(self):
        result = expected_value(2.5, 0.6)
        assert result > 0

    def test_expected_value_negative(self):
        result = expected_value(1.5, 0.3)
        assert result < 0


class TestClosingLineValue:
    def test_closing_line_value(self):
        result = closing_line_value(0.55, 2.0)
        assert result == pytest.approx(0.55 - 0.5)


class TestCalculateROI:
    def test_calculate_roi_positive(self):
        bets = [
            {"stake": 100, "payout": 200},
            {"stake": 100, "payout": 150},
        ]
        result = calculate_roi(bets)
        assert result > 0

    def test_calculate_roi_zero(self):
        bets = [
            {"stake": 100, "payout": 100},
        ]
        result = calculate_roi(bets)
        assert result == 0.0
