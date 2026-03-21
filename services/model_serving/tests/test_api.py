from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

from main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    api_key = "test-api-key"
    with patch.dict("os.environ", {"API_KEY": api_key}, clear=False):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"X-API-Key": api_key},
        ) as ac:
            yield ac


@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "model-serving"


@pytest.mark.asyncio
async def test_get_prediction(client):
    match_id = "test-match-123"
    response = await client.get(f"/api/v1/predictions/{match_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["match_id"] == match_id
    assert "probabilities" in data
    assert "home_win" in data["probabilities"]
    assert "draw" in data["probabilities"]
    assert "away_win" in data["probabilities"]
    assert "shap_explanation" in data


@pytest.mark.asyncio
async def test_batch_prediction(client):
    request_data = {
        "matches": [
            {"match_id": "match-1", "home_team": "Team A", "away_team": "Team B"},
            {"match_id": "match-2", "home_team": "Team C", "away_team": "Team D"},
        ]
    }
    response = await client.post("/api/v1/predictions/batch", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert "predictions" in data
    assert len(data["predictions"]) == 2


@pytest.mark.asyncio
async def test_value_bets(client):
    response = await client.get("/api/v1/value-bets")
    assert response.status_code == 200
    data = response.json()
    assert "value_bets" in data


@pytest.mark.asyncio
async def test_value_bets_with_date(client):
    response = await client.get("/api/v1/value-bets?date=2026-03-05")
    assert response.status_code == 200
    data = response.json()
    assert data["date"] == "2026-03-05"


@pytest.mark.asyncio
async def test_value_bets_with_min_edge(client):
    response = await client.get("/api/v1/value-bets?min_edge=0.05")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_report(client):
    match_id = "test-match-123"
    response = await client.get(f"/api/v1/reports/{match_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["match_id"] == match_id
    assert "home_win_prob" in data
    assert "draw_prob" in data
    assert "away_win_prob" in data
    assert "shap_explanation" in data


@pytest.mark.asyncio
async def test_get_report_pdf(client):
    match_id = "test-match-123"
    response = await client.get(f"/api/v1/reports/{match_id}/pdf")
    assert response.status_code == 200
    data = response.json()
    assert "pdf_url" in data


@pytest.mark.asyncio
async def test_list_models(client):
    response = await client.get("/models")
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert len(data["models"]) > 0


@pytest.mark.asyncio
async def test_prediction_response_schema(client):
    response = await client.get("/api/v1/predictions/test-match")
    assert response.status_code == 200
    data = response.json()

    required_fields = [
        "match_id",
        "home_team",
        "away_team",
        "league",
        "model",
        "model_version",
        "probabilities",
        "predicted_score",
        "calibrated",
        "brier_score_trailing_100",
        "value_bets",
        "shap_explanation",
        "generated_at",
    ]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"

    assert "home_win" in data["probabilities"]
    assert "draw" in data["probabilities"]
    assert "away_win" in data["probabilities"]

    assert "home" in data["predicted_score"]
    assert "away" in data["predicted_score"]


@pytest.mark.asyncio
async def test_shap_explanation_schema(client):
    response = await client.get("/api/v1/predictions/test-match")
    data = response.json()

    shap = data["shap_explanation"]
    assert "positive_drivers" in shap
    assert "negative_drivers" in shap

    for driver in shap["positive_drivers"]:
        assert "feature" in driver
        assert "impact" in driver
        assert "label" in driver


@pytest.mark.asyncio
async def test_value_bet_schema(client):
    response = await client.get("/api/v1/value-bets")
    data = response.json()

    for bet in data["value_bets"]:
        assert "match_id" in bet
        assert "selection" in bet
        assert "model_prob" in bet
        assert "best_odds" in bet
        assert "implied_prob" in bet
        assert "edge" in bet
        assert "kelly_stake_pct" in bet
        assert "sportsbook" in bet
