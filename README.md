# SportAnalyst

XGBoost + Poisson ensemble model for football match outcome prediction. Trained on 8,700+ matches across 9 leagues (Premier League, La Liga, Bundesliga, Serie A, Ligue 1, Eredivisie, J1 League, Brasileirao, MLS).

## What it does

- Predicts **home win / draw / away win** probabilities for upcoming fixtures
- Uses 43 features: form stats, ELO ratings, head-to-head, rest days, league averages, and betting odds
- Serves predictions via a FastAPI backend + Next.js dashboard

## Model performance

| Metric | Value |
|--------|-------|
| Accuracy | ~49% (vs 45% baseline) |
| Model | XGBoost + Poisson ensemble |
| Training data | 2022-2024 seasons |
| Test data | 2026 season |

## Quick start

```bash
# Docker (recommended)
docker compose -f docker-compose.deploy.yml up --build

# Local
pip install -e libs/
uvicorn services.model_serving.src.main:app --port 8005
```

Dashboard: `http://localhost:3000` | API: `http://localhost:8005`

## Project structure

```
libs/sports_common/    Shared utilities (DB config, models, feature engineering)
services/
  model_serving/       FastAPI backend + ML model serving
  feature_engine/      Feature computation pipeline
  model_training/      Training pipeline
  biometric_service/   Player biometric data
  nlp_service/         Text analysis
frontend/              Next.js dashboard
scripts/               Training, prediction, odds fetching
models/                Trained model artifacts
```

## API endpoints

- `GET /matches/upcoming` — upcoming fixtures with predictions
- `GET /predictions/accuracy` — model accuracy by confidence tier
- `GET /value-bets` — odds vs model probability comparison
- `GET /api/models` — available model versions

## Tech stack

- **ML**: XGBoost, scikit-learn, Poisson regression, SHAP
- **Backend**: FastAPI, SQLAlchemy, asyncpg, PostgreSQL
- **Frontend**: Next.js, Tailwind CSS, Recharts
- **Infra**: Docker Compose, GitHub Actions CI/CD
- **Data**: the-odds-api.com, football-data.org

## Odds integration

The model incorporates live betting odds (implied probabilities) as features. Odds are fetched from the-odds-api.com across 8 leagues. Free tier provides current odds only; historical odds accumulate over time.

## License

Private — not for distribution.
