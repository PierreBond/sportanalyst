# SportAnalyst

Football match outcome prediction (home win / draw / away win) served through a
FastAPI backend to a Next.js dashboard. Free data only: football-data.org for
results and fixtures, the-odds-api.com for prices. Runs locally on Docker
Compose.

## What it does

- Predicts **home win / draw / away win** probabilities for upcoming fixtures
- Compares the served model against bookmaker prices with the margin removed
  (`/value-bets` board), so every number on screen can be checked
- Serves predictions via a FastAPI backend + Next.js dashboard

## Model

| Metric | Value |
|--------|-------|
| Model | Logistic regression + Poisson goal models (`v4.8_logistic`) |
| Features | 11 market-independent for the outcome model: Elo difference, goals scored/conceded (last 5), form, rest days, league goal average, league draw rate |
| Goal model | 37 features for expected goals: rolling form and goals, rest days, league averages, head-to-head, Elo. Standardised, no odds and no label-encoded club ids |
| Training data | 2005–2026 history (45,250 matches, 9 leagues) |
| Test data | 2026 season so far (949 matches, never used for fitting) |
| Held-out accuracy | **measured on every retrain — see `/models`** (v4.8: 52.9%, Brier 0.1967, base rate 45.3%) |
| Calibration | chosen out-of-fold among identity / isotonic / vector scaling; the winner is recorded in the metadata |

The model deliberately reads **no odds or implied probabilities**, so the board
compares two independent estimates instead of echoing the bookmaker.

Club history is keyed on a canonical club name: the same club is stored under
several team ids in the source data, and rating one id at a time split its
history and left its Elo unrated.

The retrain windows are date based, because the season labels in the source
data span parts of two real seasons: everything before the selection window
fits the models, the selection window (the season before the current one)
picks the blend weight by log-loss, and the current season is only ever used
to report. The calibration method is picked the same way, by cross-validated
log-loss on the out-of-fold block.

### Free history

```bash
python scripts/ingest_history.py --dry-run   # report the club mapping
python scripts/ingest_history.py             # ingest (idempotent)
```

Pulls every result from football-data.co.uk for the six European leagues from
2005/06 to 2021/22 (35,763 matches, no account or card needed). Without it a
promoted club has almost no history, gets the default Elo and produces the
absurd edges on the board. The script is idempotent: matches are keyed on
`(external_id, provider)` and any match that already exists (same league,
date and clubs) is skipped.

## Quick start

```bash
# Docker (recommended)
docker compose -f docker-compose.deploy.yml up --build

# Local
pip install -e libs/
uvicorn services.model_serving.src.main:app --port 8005
```

Dashboard: `http://localhost:3000` | API: `http://localhost:8005`

## Retraining

```bash
python scripts/retrain_logreg.py
```

Rewrites `models/predictor.joblib`, `models/poisson.joblib`,
`models/calibrator.json` and `models/predictor_metadata.json`, and prints the
held-out accuracy, Brier score and base rate it measured on the untouched
season. Rebuild the backend image afterwards so the container serves the new
artifacts.

Bump `model_version` in `scripts/retrain_logreg.py` when you retrain: the batch
prediction upsert only replaces a stored row when the model version differs,
so a reused version leaves predictions from the previous artifact in the table.

## Results refresh

```bash
python scripts/ingest_all_leagues.py
```

Pulls the current season's fixtures and results for the seven leagues from
football-data.org (free tier, 10 requests/minute) and upserts them on
`(external_id, provider)`, so re-running never duplicates a fixture. The
`odds-refresh` container runs this before the odds pull and the prediction
batch every 24 hours.

It matters more than it looks: the model's form and Elo features come from
results in the database, so a stale results table makes the model disagree
with the market on stale form and the board fills up with fake "value" bets.
Refresh the results first, then retrain.

## Project structure

```
libs/sports_common/    Shared utilities (DB config, models, team canonicalization)
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

- `GET /api/v1/matches/upcoming` — upcoming fixtures
- `GET /api/v1/predictions/{match_id}` — served prediction for one fixture
- `GET /api/v1/value-bets` — model probabilities vs sportsbook prices
- `GET /api/v1/markets/{match_id}` — goal-model markets (xG proxy, totals, BTTS)
- `GET /models` — served model card: version, accuracy, Brier, blend weight

## Tech stack

- **ML**: scikit-learn (logistic regression, isotonic/vector calibration), Poisson regression
- **Backend**: FastAPI, SQLAlchemy, asyncpg, PostgreSQL
- **Frontend**: Next.js, Tailwind CSS, self-hosted IBM Plex
- **Infra**: Docker Compose, GitHub Actions CI/CD
- **Data**: football-data.org, the-odds-api.com (free tier)

## Odds integration

Prices come from the-odds-api.com across 8 leagues and are stored as snapshots.
The free tier provides current odds only, so history accumulates as fixtures
approach. Roughly 3% of upcoming fixtures carry a price at any time.

## License

Private — not for distribution.
