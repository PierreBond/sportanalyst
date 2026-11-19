"""Tests for the PDF report renderer."""

from __future__ import annotations

from services.model_serving.src.pdf import render_match_report_pdf


REPORT = {
    "home_team": "SC Corinthians Paulista",
    "away_team": "Botafogo FR",
    "league": "brasileirao",
    "scheduled_at": "2026-11-22T00:00:00+00:00",
    "generated_at": "2026-11-19T00:00:00+00:00",
    "model_version": "v4.8_logistic",
    "probabilities": {"home_win": 0.3562, "draw": 0.3002, "away_win": 0.3436},
    "shap_explanation": {
        "positive_drivers": [
            {"label": "Elo rating advantage", "impact": 0.21},
            {"label": "Home goals scored (last 5)", "impact": 0.08},
        ],
        "negative_drivers": [
            {"label": "Home team rest days", "impact": -0.05},
        ],
    },
}

METADATA = {
    "model_version": "v4.8_logistic",
    "accuracy": 0.529,
    "brier_score": 0.1967,
    "accuracy_base_rate": 0.4531,
}

XG = {"home": 1.23, "away": 0.98, "total": 2.21}


def test_renders_a_valid_pdf():
    pdf = render_match_report_pdf(REPORT, METADATA, XG)

    assert pdf.startswith(b"%PDF-")
    assert pdf.rstrip().endswith(b"%%EOF")
    assert len(pdf) > 1000


def test_pdf_contains_the_report_content():
    pdf = render_match_report_pdf(REPORT, METADATA, XG)

    for needle in [
        b"Corinthians",
        b"Botafogo",
        b"v4.8_logistic",
        b"52.9%",
        b"0.1967",
        b"Elo rating advantage",
        b"not an edge signal",
    ]:
        assert needle in pdf, f"missing {needle!r} in the rendered PDF"


def test_renders_without_optional_sections():
    """Missing SHAP drivers, xG and metadata must not break the render."""
    minimal = {
        "home_team": "Home FC",
        "away_team": "Away FC",
        "probabilities": {"home_win": 0.4, "draw": 0.3, "away_win": 0.3},
    }
    pdf = render_match_report_pdf(minimal, None, None)

    assert pdf.startswith(b"%PDF-")
    assert pdf.rstrip().endswith(b"%%EOF")
    assert b"Home FC" in pdf
