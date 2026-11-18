"""Regression test: the home and away rolling features must describe
different clubs.

train_model.add_rolling used to map the rolling features back with
groupby("match_id").first() over a frame holding both the home and the away
row of every match, so the "home" and "away" form features came out
identical -- the model could not tell the two teams apart on form.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from train_model import add_h2h_features, engineer_features  # noqa: E402

ROWS = [
    # match, date, home, away, hg, ag
    ("m1", "2024-01-01", "Alpha FC", "Beta FC", 2, 0),
    ("m2", "2024-01-08", "Alpha FC", "Gamma FC", 0, 3),
    ("m3", "2024-01-15", "Beta FC", "Gamma FC", 1, 1),
]


def _frame() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "match_id": mid,
            "league": "L1",
            "season": "2024",
            "round": str(i),
            "scheduled_at": pd.Timestamp(date, tz="UTC"),
            "home_score": hg,
            "away_score": ag,
            "home_team": home,
            "away_team": away,
            "home_team_id": f"id_{home}",
            "away_team_id": f"id_{away}",
        }
        for i, (mid, date, home, away, hg, ag) in enumerate(ROWS)
    ])


def test_home_and_away_form_features_differ():
    df, _ = engineer_features(_frame())
    last = df[df["match_id"] == "m3"].iloc[0]

    # Beta (home) last scored 0 goals away at Alpha; Gamma (away) last scored
    # 3 goals away at Alpha.
    assert last["home_gf_avg_last5"] == 0.0
    assert last["away_gf_avg_last5"] == 3.0
    assert last["home_gf_avg_last5"] != last["away_gf_avg_last5"]

    # goals conceded: Beta conceded 2 at Alpha, Gamma conceded 0 at Alpha
    assert last["home_ga_avg_last5"] == 2.0
    assert last["away_ga_avg_last5"] == 0.0


def test_form_features_are_not_duplicated():
    df, _ = engineer_features(_frame())
    for w in (3, 5, 10):
        assert (
            df[f"home_gf_avg_last{w}"] != df[f"away_gf_avg_last{w}"]
        ).any(), f"home and away goals features are identical at window {w}"
        assert (
            df[f"home_form_last{w}"] != df[f"away_form_last{w}"]
        ).any(), f"home and away form features are identical at window {w}"


def test_venue_split_features_use_the_right_team():
    df, _ = engineer_features(_frame())
    last = df[df["match_id"] == "m3"].iloc[0]

    # home_h = the home team's form at home (Beta has no home game yet)
    # away_a = the away team's form away (Gamma scored 3 away at Alpha)
    assert last["home_h_gf_avg_last5"] == 0.0
    assert last["away_a_gf_avg_last5"] == 3.0


H2H_ROWS = [
    # match, date, home, away, hg, ag
    ("h1", "2024-01-01", "Alpha FC", "Delta FC", 2, 0),
    ("h2", "2024-01-08", "Delta FC", "Alpha FC", 1, 1),
    ("h3", "2024-01-15", "Alpha FC", "Delta FC", 0, 3),
    ("h4", "2024-01-22", "Delta FC", "Alpha FC", 4, 1),
    ("h5", "2024-02-01", "Beta FC", "Gamma FC", 1, 0),
]


def _h2h_frame() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "match_id": mid,
            "scheduled_at": pd.Timestamp(date, tz="UTC"),
            "home_team": home,
            "away_team": away,
            "home_score": hg,
            "away_score": ag,
        }
        for mid, date, home, away, hg, ag in H2H_ROWS
    ])


def _naive_h2h(df: pd.DataFrame) -> dict[str, tuple[float, float, float, float]]:
    """Reference implementation: look up every prior meeting of the pair."""
    out: dict[str, tuple[float, float, float, float]] = {}
    for _, row in df.iterrows():
        prior = df[
            ((df["home_team"] == row["home_team"]) & (df["away_team"] == row["away_team"]))
            | ((df["home_team"] == row["away_team"]) & (df["away_team"] == row["home_team"]))
        ]
        prior = prior[prior["scheduled_at"] < row["scheduled_at"]].tail(5)
        if prior.empty:
            out[row["match_id"]] = (0.0, 0.0, 0.5, 0.26)
            continue
        home_was_home = prior["home_team"] == row["home_team"]
        hg = prior["home_score"].where(home_was_home, prior["away_score"])
        ag = prior["away_score"].where(home_was_home, prior["home_score"])
        out[row["match_id"]] = (
            float(hg.mean()),
            float(ag.mean()),
            float((hg > ag).mean()),
            float((hg == ag).mean()),
        )
    return out


def test_h2h_features_match_the_pair_lookup():
    df = add_h2h_features(_h2h_frame())
    expected = _naive_h2h(_h2h_frame())
    for row in df.itertuples():
        want = expected[row.match_id]
        got = (
            row.h2h_home_gf_avg,
            row.h2h_away_gf_avg,
            row.h2h_home_wins,
            row.h2h_draw_rate,
        )
        assert got == pytest.approx(want), f"{row.match_id}: {got} != {want}"


def test_h2h_features_follow_the_home_club_perspective():
    df = add_h2h_features(_h2h_frame()).set_index("match_id")

    # h3: Alpha at home, prior meetings h1 (Alpha 2-0 Delta) and h2 (1-1)
    # -> Alpha scored 2 and 1, Delta scored 0 and 1
    assert df.loc["h3", "h2h_home_gf_avg"] == pytest.approx(1.5)
    assert df.loc["h3", "h2h_away_gf_avg"] == pytest.approx(0.5)
    assert df.loc["h3", "h2h_home_wins"] == pytest.approx(0.5)
    assert df.loc["h3", "h2h_draw_rate"] == pytest.approx(0.5)

    # h4: Delta at home, prior meetings h1, h2, h3
    # -> Delta scored 0, 1, 3; Alpha scored 2, 1, 0; one draw, one Delta win
    assert df.loc["h4", "h2h_home_gf_avg"] == pytest.approx(4 / 3)
    assert df.loc["h4", "h2h_away_gf_avg"] == pytest.approx(1.0)
    assert df.loc["h4", "h2h_home_wins"] == pytest.approx(1 / 3)
    assert df.loc["h4", "h2h_draw_rate"] == pytest.approx(1 / 3)

    # h5: a pair with no prior meeting
    assert df.loc["h5", "h2h_home_gf_avg"] == 0.0
    assert df.loc["h5", "h2h_home_wins"] == 0.5
    assert df.loc["h5", "h2h_draw_rate"] == 0.26
