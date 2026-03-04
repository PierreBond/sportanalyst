# Sports Prediction System — AI Agent Coding Guide

> **Purpose:** This document is the single source of truth for any AI coding agent working on this project. It contains every requirement, convention, file structure, data schema, API contract, coding rule, and step-by-step instruction needed to build the system without human clarification.
>
> **Date:** March 3, 2026
> **Reference:** `Building A Sports Prediction System.md`, `Implementation Plan.md`

---

## Table of Contents

- [A. Global Development Rules](#a-global-development-rules)
- [B. Repository & Folder Structure](#b-repository--folder-structure)
- [C. Environment & Tooling Setup](#c-environment--tooling-setup)
- [D. Database Schema & Migrations](#d-database-schema--migrations)
- [E. Module 1 — Data Ingestion Service](#e-module-1--data-ingestion-service)
- [F. Module 2 — Data Adapters (API Integrations)](#f-module-2--data-adapters-api-integrations)
- [G. Module 3 — Feature Engineering Pipeline](#g-module-3--feature-engineering-pipeline)
- [H. Module 4 — ML Model Training & Registry](#h-module-4--ml-model-training--registry)
- [I. Module 5 — Biometric Integration Service](#i-module-5--biometric-integration-service)
- [J. Module 6 — NLP & Sentiment Service](#j-module-6--nlp--sentiment-service)
- [K. Module 7 — Calibration & Betting Strategy Engine](#k-module-7--calibration--betting-strategy-engine)
- [L. Module 8 — Explainability & Reporting Service](#l-module-8--explainability--reporting-service)
- [M. Module 9 — Model Serving API](#m-module-9--model-serving-api)
- [N. Module 10 — Frontend Dashboard](#n-module-10--frontend-dashboard)
- [O. Infrastructure as Code](#o-infrastructure-as-code)
- [P. CI/CD Pipeline](#p-cicd-pipeline)
- [Q. Testing Strategy](#q-testing-strategy)
- [R. Coding Roadmap (Step-by-Step Build Order)](#r-coding-roadmap-step-by-step-build-order)
- [S. Agent Workflow Protocol (MANDATORY)](#s-agent-workflow-protocol-mandatory)

---

## A. Global Development Rules

Every AI agent (and human contributor) MUST follow these rules without exception.

### A.1 Language & Runtime

| Component | Language | Runtime / Framework |
|:---|:---|:---|
| All backend services | **Python 3.11+** | FastAPI (REST & WebSocket) |
| Feature pipeline | **Python 3.11+** | PySpark (Spark 3.5+) |
| ML training scripts | **Python 3.11+** | PyTorch 2.x, scikit-learn, XGBoost |
| NLP module | **Python 3.11+** | Hugging Face Transformers, spaCy |
| Frontend dashboard | **TypeScript 5.x** | Next.js 14+ (App Router), React 18+ |
| Infrastructure | **HCL / YAML** | Terraform, Kubernetes manifests |

### A.2 Code Style & Formatting

```
RULE-01  Python: Format with `ruff format` (line-length = 100). Lint with `ruff check`.
RULE-02  Python: Type-hint EVERY function signature (params + return). Use `from __future__ import annotations`.
RULE-03  Python: Docstrings are MANDATORY for every public class and function (Google-style).
RULE-04  Python: No bare `except:`. Always catch specific exceptions.
RULE-05  Python: Use `pathlib.Path` — never `os.path` string concatenation.
RULE-06  TypeScript: Format with Prettier (printWidth: 100). Lint with ESLint (strict config).
RULE-07  TypeScript: Strict mode enabled (`"strict": true` in tsconfig).
RULE-08  TypeScript: Prefer `interface` over `type` for object shapes.
RULE-09  All code: Max function length = 50 lines. Extract helpers if exceeded.
RULE-10  All code: No magic numbers. Use named constants or enums.
RULE-11  All code: No `print()` — use structured logging (Python: `structlog`; TS: `pino`).
RULE-12  Commits: Conventional Commits format — `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`.
RULE-13  Branches: `feat/<module>-<short-desc>`, `fix/<module>-<short-desc>`, `chore/<desc>`.
RULE-14  Every PR must pass ALL CI checks (lint, type-check, tests) before merge.
```

### A.3 Environment Variables & Secrets

```
RULE-15  NEVER hard-code API keys, passwords, or connection strings in source code.
RULE-16  All secrets go in `.env` files (Git-ignored) locally and K8s Secrets / Vault in prod.
RULE-17  Use pydantic `BaseSettings` for config classes — validate on startup.
RULE-18  Every service must fail-fast with a clear error if a required env var is missing.
```

### A.4 Error Handling & Logging

```
RULE-19  All API endpoints return structured error JSON: {"error": str, "detail": str, "code": int}.
RULE-20  Log every external API call (provider, endpoint, status, latency) at INFO level.
RULE-21  Log every exception with full traceback at ERROR level.
RULE-22  Include a `correlation_id` (UUID) in every log line, propagated via HTTP headers.
RULE-23  Use `structlog` with JSON output processor in all Python services.
```

### A.5 Data Safety Rules (CRITICAL)

```
RULE-24  NEVER include future information in training features. Every feature must use only
         data available at or before the prediction timestamp.
RULE-25  All temporal joins MUST use `<=` on the timestamp column — never `<` + 1 day hack.
RULE-26  All train/test splits MUST be chronological. NEVER use random cross-validation for
         time-series sports data.
RULE-27  Write an automated data-leakage test for every new feature: assert that the feature
         timestamp is <= the prediction timestamp for every row.
RULE-28  When in doubt, use the OPENING line value, not the CLOSING line, to avoid look-ahead bias.
```

---

## B. Repository & Folder Structure

```
sports-prediction-system/
│
├── .github/
│   └── workflows/
│       ├── ci.yml                     # Lint → type-check → test on every PR
│       ├── cd-staging.yml             # Deploy to staging on merge to `develop`
│       └── cd-production.yml          # Deploy to prod on merge to `main`
│
├── infra/                             # Infrastructure as Code
│   ├── terraform/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── modules/
│   │       ├── kafka/
│   │       ├── kubernetes/
│   │       ├── postgres/
│   │       └── mlflow/
│   ├── k8s/
│   │   ├── base/
│   │   │   ├── namespace.yml
│   │   │   └── configmap.yml
│   │   └── services/
│   │       ├── ingestion/
│   │       │   ├── deployment.yml
│   │       │   ├── service.yml
│   │       │   └── hpa.yml
│   │       ├── feature-engine/
│   │       ├── model-serving/
│   │       ├── nlp-service/
│   │       ├── biometric-service/
│   │       ├── reporting-service/
│   │       └── api-gateway/
│   └── docker/
│       ├── Dockerfile.base            # Shared Python base image
│       ├── Dockerfile.spark           # Spark worker image
│       └── Dockerfile.frontend        # Next.js production image
│
├── libs/                              # Shared Python library (installed as local package)
│   ├── pyproject.toml
│   └── sports_common/
│       ├── __init__.py
│       ├── config.py                  # BaseSettings-based config loader
│       ├── logging.py                 # structlog setup
│       ├── kafka_client.py            # Producer/consumer wrappers
│       ├── db.py                      # Async SQLAlchemy engine + session factory
│       ├── schemas/                   # Pydantic models shared across services
│       │   ├── __init__.py
│       │   ├── events.py              # MatchEvent, GoalEvent, SubstitutionEvent, etc.
│       │   ├── odds.py                # OddsSnapshot, LineMovement, etc.
│       │   ├── biometrics.py          # PlayerBiometric, ACWR, WellnessScore, etc.
│       │   ├── sentiment.py           # SentimentResult, NewsAlert, etc.
│       │   ├── predictions.py         # MatchPrediction, ProbabilityDistribution, etc.
│       │   └── features.py            # FeatureVector, FeatureMetadata
│       ├── constants.py               # Sport enums, league IDs, position codes, etc.
│       └── utils/
│           ├── time.py                # Timezone-aware datetime helpers
│           ├── math.py                # Poisson, Kelly, Brier score functions
│           └── data_guard.py          # Data-leakage assertion helpers
│
├── services/
│   ├── ingestion/                     # Module 1 — Data Ingestion Service
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   ├── main.py               # FastAPI app entrypoint
│   │   │   ├── consumers/             # Kafka consumers (one per topic)
│   │   │   ├── producers/             # Kafka producers (write to processed topics)
│   │   │   ├── adapters/              # Module 2 — API provider adapters
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base_adapter.py    # Abstract adapter class
│   │   │   │   ├── sportsdataio.py
│   │   │   │   ├── api_sports.py
│   │   │   │   ├── mysportsfeeds.py
│   │   │   │   ├── sportmonks.py
│   │   │   │   ├── oddsjam.py
│   │   │   │   ├── opticodds.py
│   │   │   │   ├── catapult.py
│   │   │   │   └── whoop.py
│   │   │   ├── validators/            # Schema validators for incoming data
│   │   │   └── health.py              # Health/readiness endpoints
│   │   └── tests/
│   │       ├── conftest.py
│   │       ├── test_adapters/
│   │       └── test_validators/
│   │
│   ├── feature_engine/                # Module 3 — Feature Engineering
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   ├── main.py               # Spark job entrypoint
│   │   │   ├── temporal.py            # Rolling windows, lag, decay, momentum
│   │   │   ├── market.py             # Odds-derived features (RLM, CLV, implied prob)
│   │   │   ├── spatial.py            # GNN-based features (advanced, Phase 2)
│   │   │   ├── biometric.py          # ACWR, wellness features
│   │   │   ├── sentiment.py          # Aggregated sentiment scores
│   │   │   └── store.py              # Feature store writer (Feast or custom)
│   │   └── tests/
│   │
│   ├── model_training/                # Module 4 — ML Training & Registry
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   ├── train.py              # Unified training entrypoint (CLI)
│   │   │   ├── models/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── poisson.py        # Poisson regression model
│   │   │   │   ├── bayesian.py       # Bayesian inference (team skill)
│   │   │   │   ├── random_forest.py  # sklearn RandomForest wrapper
│   │   │   │   ├── xgboost_model.py  # XGBoost wrapper
│   │   │   │   ├── cnn.py            # CNN spatial module
│   │   │   │   ├── lstm.py           # LSTM sequential module
│   │   │   │   ├── cnn_lstm.py       # Combined CNN-LSTM
│   │   │   │   ├── transformer.py    # Transformer attention model
│   │   │   │   ├── tabnet.py         # TabNet model
│   │   │   │   └── base_model.py     # Abstract base: train(), predict(), save(), load()
│   │   │   ├── data_loader.py        # Reads from feature store, applies chrono split
│   │   │   ├── evaluator.py          # Metrics: accuracy, Brier score, log-loss, CLV
│   │   │   └── registry.py           # MLflow model logging & promotion
│   │   ├── configs/
│   │   │   ├── poisson.yaml
│   │   │   ├── xgboost.yaml
│   │   │   ├── transformer.yaml
│   │   │   └── ...                   # One config per model
│   │   └── tests/
│   │
│   ├── nlp_service/                   # Module 6 — NLP & Sentiment
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   ├── main.py               # FastAPI app
│   │   │   ├── scrapers/
│   │   │   │   ├── twitter.py
│   │   │   │   ├── reddit.py
│   │   │   │   └── news_rss.py
│   │   │   ├── preprocessing.py      # Tokenization, cleaning, POS tagging
│   │   │   ├── vectorizer.py         # TF-IDF, Word2Vec, BERT embeddings
│   │   │   ├── classifier.py         # Sentiment model (BERT fine-tuned)
│   │   │   ├── event_detector.py     # Breaking news detection (injury, lineup)
│   │   │   └── publisher.py          # Publishes SentimentResult to Kafka
│   │   └── tests/
│   │
│   ├── biometric_service/             # Module 5 — Biometrics
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   ├── main.py               # FastAPI app
│   │   │   ├── acwr.py               # ACWR calculation
│   │   │   ├── injury_risk.py        # Injury-risk classifier
│   │   │   ├── wellness.py           # Team wellness aggregator
│   │   │   └── publisher.py          # Publishes biometric features to Kafka
│   │   └── tests/
│   │
│   ├── model_serving/                 # Module 9 — Model Serving API
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   ├── main.py               # FastAPI app (REST + WebSocket)
│   │   │   ├── predictor.py          # Loads model from MLflow, runs inference
│   │   │   ├── calibrator.py         # Post-hoc calibration (Platt/isotonic)
│   │   │   ├── betting.py            # Kelly Criterion, value-bet detection
│   │   │   ├── explainer.py          # SHAP computation
│   │   │   └── cache.py              # Redis prediction cache
│   │   └── tests/
│   │
│   └── reporting_service/             # Module 8 — Reports
│       ├── pyproject.toml
│       ├── src/
│       │   ├── __init__.py
│       │   ├── main.py               # FastAPI app
│       │   ├── report_builder.py     # Assembles Match Research Snapshot
│       │   ├── templates/
│       │   │   ├── match_report.html # Jinja2 template
│       │   │   └── match_report.md
│       │   └── pdf_exporter.py       # HTML → PDF via weasyprint
│       └── tests/
│
├── frontend/                          # Module 10 — Next.js Dashboard
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.js
│   ├── tailwind.config.ts
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx              # Dashboard home
│   │   │   ├── matches/
│   │   │   │   ├── page.tsx          # Match list / upcoming
│   │   │   │   └── [matchId]/
│   │   │   │       └── page.tsx      # Single match detail + prediction
│   │   │   ├── players/
│   │   │   │   └── [playerId]/
│   │   │   │       └── page.tsx      # Player biometrics / readiness
│   │   │   ├── market/
│   │   │   │   └── page.tsx          # Odds dashboard, line movement
│   │   │   ├── reports/
│   │   │   │   └── page.tsx          # Generated reports
│   │   │   └── settings/
│   │   │       └── page.tsx
│   │   ├── components/
│   │   │   ├── PredictionCard.tsx
│   │   │   ├── LineMovementChart.tsx
│   │   │   ├── SHAPWaterfall.tsx
│   │   │   ├── BiometricGauge.tsx
│   │   │   ├── SentimentBadge.tsx
│   │   │   └── ...
│   │   ├── lib/
│   │   │   ├── api.ts               # Typed fetch wrappers for backend
│   │   │   └── ws.ts                # WebSocket hook for live updates
│   │   └── types/
│   │       └── index.ts              # Mirrors backend Pydantic schemas
│   └── tests/
│
├── scripts/
│   ├── seed_db.py                    # Load historical data into Postgres
│   ├── backtest.py                   # Full chronological backtest runner
│   └── generate_report.py            # CLI for one-off report generation
│
├── notebooks/                         # Jupyter exploration (NOT production code)
│   ├── eda_historical_data.ipynb
│   ├── feature_exploration.ipynb
│   └── model_comparison.ipynb
│
├── .env.example                       # Template for all env vars
├── .gitignore
├── docker-compose.yml                 # Local dev: Kafka, Postgres, Redis, MLflow
├── pyproject.toml                     # Root workspace (uv / poetry workspace)
├── Makefile                           # Common commands: lint, test, up, down, train
└── README.md
```

---

## C. Environment & Tooling Setup

### C.1 Prerequisites

```bash
# Required on dev machine
python >= 3.11
node >= 20 LTS
docker >= 24
docker-compose >= 2.20
kubectl >= 1.28
terraform >= 1.6
uv >= 0.1  # Python package installer (or poetry >= 1.7)
```

### C.2 Local Bootstrap (Step-by-Step)

```bash
# 1. Clone repository
git clone <repo-url> && cd sports-prediction-system

# 2. Copy env file
cp .env.example .env
# Fill in API keys: SPORTSDATAIO_KEY, ODDSJAM_KEY, OPTICODDS_KEY, etc.

# 3. Start infrastructure containers
docker-compose up -d   # Starts Kafka, Zookeeper, Postgres, Redis, MLflow

# 4. Install shared library
cd libs && uv pip install -e ".[dev]" && cd ..

# 5. Install each service
for svc in ingestion feature_engine model_training nlp_service biometric_service model_serving reporting_service; do
  cd services/$svc && uv pip install -e ".[dev]" && cd ../..
done

# 6. Run database migrations
cd services/ingestion && alembic upgrade head && cd ../..

# 7. Seed historical data
python scripts/seed_db.py --seasons 2021 2022 2023 2024 2025

# 8. Verify everything runs
make lint    # ruff check across all services
make test    # pytest across all services
```

### C.3 Required `.env` Variables

```env
# --- Database ---
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/sportspred
DATABASE_URL_SYNC=postgresql://user:pass@localhost:5432/sportspred

# --- Kafka ---
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# --- Redis ---
REDIS_URL=redis://localhost:6379/0

# --- MLflow ---
MLFLOW_TRACKING_URI=http://localhost:5000

# --- Sports Data APIs ---
SPORTSDATAIO_API_KEY=
API_SPORTS_KEY=
MYSPORTSFEEDS_API_KEY=
SPORTMONKS_API_KEY=

# --- Odds / Market APIs ---
ODDSJAM_API_KEY=
OPTICODDS_API_KEY=

# --- Biometric APIs ---
CATAPULT_API_KEY=
CATAPULT_BASE_URL=
WHOOP_CLIENT_ID=
WHOOP_CLIENT_SECRET=

# --- NLP / Scraping ---
TWITTER_BEARER_TOKEN=
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=

# --- Service Ports ---
INGESTION_PORT=8001
NLP_SERVICE_PORT=8002
BIOMETRIC_SERVICE_PORT=8003
MODEL_SERVING_PORT=8004
REPORTING_SERVICE_PORT=8005
```

---

## D. Database Schema & Migrations

Use **Alembic** for migrations. All tables in `public` schema.

### D.1 Core Tables

```sql
-- Teams
CREATE TABLE teams (
    team_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id   VARCHAR(50) NOT NULL,       -- provider-specific ID
    provider      VARCHAR(30) NOT NULL,        -- 'sportsdataio', 'api_sports', etc.
    name          VARCHAR(120) NOT NULL,
    short_name    VARCHAR(10),
    league        VARCHAR(60) NOT NULL,
    country       VARCHAR(60),
    created_at    TIMESTAMPTZ DEFAULT now(),
    UNIQUE (external_id, provider)
);

-- Players
CREATE TABLE players (
    player_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id   VARCHAR(50) NOT NULL,
    provider      VARCHAR(30) NOT NULL,
    team_id       UUID REFERENCES teams(team_id),
    name          VARCHAR(150) NOT NULL,
    position      VARCHAR(30),
    date_of_birth DATE,
    created_at    TIMESTAMPTZ DEFAULT now(),
    UNIQUE (external_id, provider)
);

-- Matches
CREATE TABLE matches (
    match_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id   VARCHAR(50) NOT NULL,
    provider      VARCHAR(30) NOT NULL,
    league        VARCHAR(60) NOT NULL,
    season        VARCHAR(10) NOT NULL,        -- e.g., '2025-26'
    round         VARCHAR(30),
    home_team_id  UUID REFERENCES teams(team_id),
    away_team_id  UUID REFERENCES teams(team_id),
    scheduled_at  TIMESTAMPTZ NOT NULL,
    venue         VARCHAR(150),
    status        VARCHAR(20) DEFAULT 'scheduled', -- scheduled|live|finished|postponed
    home_score    SMALLINT,
    away_score    SMALLINT,
    created_at    TIMESTAMPTZ DEFAULT now(),
    updated_at    TIMESTAMPTZ DEFAULT now(),
    UNIQUE (external_id, provider)
);
CREATE INDEX idx_matches_scheduled ON matches(scheduled_at);
CREATE INDEX idx_matches_league_season ON matches(league, season);

-- Match Events (play-by-play)
CREATE TABLE match_events (
    event_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id      UUID REFERENCES matches(match_id) NOT NULL,
    event_type    VARCHAR(40) NOT NULL,        -- goal, shot, foul, card, substitution, etc.
    minute        SMALLINT,
    second        SMALLINT,
    team_id       UUID REFERENCES teams(team_id),
    player_id     UUID REFERENCES players(player_id),
    detail        JSONB,                        -- provider-specific event detail
    created_at    TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_events_match ON match_events(match_id);

-- Odds Snapshots
CREATE TABLE odds_snapshots (
    snapshot_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id      UUID REFERENCES matches(match_id) NOT NULL,
    sportsbook    VARCHAR(60) NOT NULL,
    market_type   VARCHAR(30) NOT NULL,        -- moneyline, spread, total, prop
    home_odds     DECIMAL(8,4),
    away_odds     DECIMAL(8,4),
    draw_odds     DECIMAL(8,4),
    spread_value  DECIMAL(6,2),
    total_value   DECIMAL(6,2),
    cash_pct_home DECIMAL(5,2),
    ticket_pct_home DECIMAL(5,2),
    captured_at   TIMESTAMPTZ NOT NULL,
    UNIQUE (match_id, sportsbook, market_type, captured_at)
);
CREATE INDEX idx_odds_match_time ON odds_snapshots(match_id, captured_at);

-- Player Biometrics
CREATE TABLE player_biometrics (
    biometric_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_id     UUID REFERENCES players(player_id) NOT NULL,
    source        VARCHAR(30) NOT NULL,        -- 'catapult', 'whoop'
    recorded_at   TIMESTAMPTZ NOT NULL,
    metric_type   VARCHAR(50) NOT NULL,        -- hrv, resting_hr, player_load, sprint_dist, etc.
    value         DECIMAL(12,4) NOT NULL,
    unit          VARCHAR(20),
    UNIQUE (player_id, source, metric_type, recorded_at)
);
CREATE INDEX idx_bio_player_time ON player_biometrics(player_id, recorded_at);

-- Sentiment Scores
CREATE TABLE sentiment_scores (
    sentiment_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type   VARCHAR(10) NOT NULL,        -- 'team' or 'player'
    entity_id     UUID NOT NULL,               -- team_id or player_id
    source        VARCHAR(30) NOT NULL,        -- twitter, reddit, news
    score         DECIMAL(5,4) NOT NULL,       -- -1.0 to 1.0
    volume        INTEGER DEFAULT 0,           -- number of texts analyzed
    captured_at   TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_sent_entity_time ON sentiment_scores(entity_type, entity_id, captured_at);

-- Feature Store (materialized feature vectors)
CREATE TABLE feature_store (
    feature_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id      UUID REFERENCES matches(match_id) NOT NULL,
    computed_at   TIMESTAMPTZ NOT NULL,         -- feature timestamp (for leakage guard)
    features      JSONB NOT NULL,               -- full feature vector as JSON
    version       VARCHAR(20) NOT NULL          -- feature pipeline version
);
CREATE INDEX idx_features_match ON feature_store(match_id);

-- Predictions
CREATE TABLE predictions (
    prediction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id      UUID REFERENCES matches(match_id) NOT NULL,
    model_name    VARCHAR(60) NOT NULL,
    model_version VARCHAR(20) NOT NULL,
    predicted_at  TIMESTAMPTZ NOT NULL,
    home_win_prob DECIMAL(5,4),
    draw_prob     DECIMAL(5,4),
    away_win_prob DECIMAL(5,4),
    predicted_home_score DECIMAL(4,2),
    predicted_away_score DECIMAL(4,2),
    shap_values   JSONB,                        -- per-feature SHAP explanations
    is_live       BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_pred_match ON predictions(match_id);
```

### D.2 Migration Rules

```
RULE-M1  Every schema change gets its own Alembic revision file.
RULE-M2  NEVER manually edit the DB schema — always go through Alembic.
RULE-M3  Revision messages: "add_<table>", "alter_<table>_add_<column>", etc.
RULE-M4  Include DOWN migration (rollback) for every UP migration.
RULE-M5  Run `alembic check` in CI to ensure no drift between models and DB.
```

---

## E. Module 1 — Data Ingestion Service

### E.1 Purpose

Central hub that connects to all external APIs, normalizes data, validates it, and publishes to Kafka topics.

### E.2 Kafka Topic Design

| Topic | Key | Value Schema | Producers | Consumers |
|:---|:---|:---|:---|:---|
| `raw.match-events` | `match_id` | `MatchEvent` | Ingestion | Feature Engine |
| `raw.odds-updates` | `match_id` | `OddsSnapshot` | Ingestion | Feature Engine |
| `raw.biometrics` | `player_id` | `PlayerBiometric` | Ingestion | Biometric Service |
| `raw.social-text` | `entity_id` | `RawTextPayload` | NLP scrapers | NLP Service |
| `processed.sentiment` | `entity_id` | `SentimentResult` | NLP Service | Feature Engine |
| `processed.biometric-features` | `player_id` | `BiometricFeature` | Biometric Service | Feature Engine |
| `processed.features` | `match_id` | `FeatureVector` | Feature Engine | Model Serving |
| `processed.predictions` | `match_id` | `MatchPrediction` | Model Serving | Reporting, Frontend |

### E.3 Adapter Interface

Every API adapter MUST implement this abstract class:

```python
# services/ingestion/src/adapters/base_adapter.py
from __future__ import annotations

import abc
from typing import AsyncIterator

from sports_common.schemas.events import MatchEvent
from sports_common.schemas.odds import OddsSnapshot


class BaseAdapter(abc.ABC):
    """Abstract base for all external data-provider adapters."""

    provider_name: str  # e.g., "sportsdataio"

    @abc.abstractmethod
    async def fetch_live_events(self, league: str) -> AsyncIterator[MatchEvent]:
        """Stream live match events for a given league."""
        ...

    @abc.abstractmethod
    async def fetch_historical_matches(
        self, league: str, season: str
    ) -> list[MatchEvent]:
        """Return all match events for a completed season."""
        ...

    @abc.abstractmethod
    async def fetch_odds(self, match_external_id: str) -> list[OddsSnapshot]:
        """Return current odds snapshots for a specific match."""
        ...

    async def health_check(self) -> bool:
        """Verify connectivity to the provider. Default: True."""
        return True
```

### E.4 Adapter Implementation Rules

```
RULE-A1  Use `httpx.AsyncClient` with connection pooling and timeouts (connect=5s, read=15s).
RULE-A2  Implement exponential backoff with jitter (max 3 retries) on transient errors (429, 502, 503).
RULE-A3  Cache provider responses in Redis with a configurable TTL (default: 30s for live, 24h for historical).
RULE-A4  Normalize all timestamps to UTC (`datetime` with `tzinfo=timezone.utc`).
RULE-A5  Map ALL provider-specific IDs to internal UUIDs via the `teams` / `players` lookup tables.
RULE-A6  If a provider returns non-JSON (XML), convert to dict using `xmltodict` before schema validation.
RULE-A7  Emit structured metrics: `data_ingestion_events_total{provider, league}` (Prometheus counter).
```

### E.5 Data Validation

```python
# services/ingestion/src/validators/event_validator.py
from sports_common.schemas.events import MatchEvent
from pydantic import ValidationError
import structlog

logger = structlog.get_logger()

def validate_event(raw: dict) -> MatchEvent | None:
    """Validate and return a MatchEvent, or None if invalid."""
    try:
        return MatchEvent.model_validate(raw)
    except ValidationError as e:
        logger.warning("invalid_event", errors=e.error_count(), raw_keys=list(raw.keys()))
        return None
```

---

## F. Module 2 — Data Adapters (API Integrations)

This is contained WITHIN the ingestion service (see E above). One file per provider.

### F.1 Provider Specifications

| Provider | Base URL | Auth | Rate Limit | Leagues |
|:---|:---|:---|:---|:---|
| SportsDataIO | `https://api.sportsdata.io/v3/` | Header: `Ocp-Apim-Subscription-Key` | 1000 req/min | NFL, NBA, MLB, NHL, soccer |
| API-SPORTS | `https://v3.football.api-sports.io/` | Header: `x-apisports-key` | 300 req/min | Global soccer, cricket |
| MySportsFeeds | `https://api.mysportsfeeds.com/v2.1/` | Basic Auth | Varies by plan | NFL, NBA, MLB, NHL |
| Sportmonks | `https://api.sportmonks.com/v3/` | Query: `api_token` | 3000 req/hour | Soccer, cricket |
| OddsJam | `https://api.oddsjam.com/v2/` | Header: `x-api-key` | 60 req/min | All major US + EU books |
| OpticOdds | `https://api.opticodds.com/api/v3/` | Header: `x-api-key` | 120 req/min | Real-time odds, lines |
| Catapult | Custom per-org | OAuth 2.0 | N/A | Team-specific biometric data |
| WHOOP | `https://api.prod.whoop.com/` | OAuth 2.0 | N/A | Player wellness & recovery |

### F.2 Adapter File Template

```python
# services/ingestion/src/adapters/sportsdataio.py
from __future__ import annotations

import httpx
from typing import AsyncIterator

from sports_common.config import settings
from sports_common.schemas.events import MatchEvent

from .base_adapter import BaseAdapter


class SportsDataIOAdapter(BaseAdapter):
    provider_name = "sportsdataio"

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url="https://api.sportsdata.io/v3/",
            headers={"Ocp-Apim-Subscription-Key": settings.SPORTSDATAIO_API_KEY},
            timeout=httpx.Timeout(connect=5.0, read=15.0),
        )

    async def fetch_live_events(self, league: str) -> AsyncIterator[MatchEvent]:
        resp = await self._client.get(f"{league}/scores/json/LiveGamesBySport/{league}")
        resp.raise_for_status()
        for raw in resp.json():
            event = self._map_to_event(raw)
            if event:
                yield event

    async def fetch_historical_matches(
        self, league: str, season: str
    ) -> list[MatchEvent]:
        resp = await self._client.get(f"{league}/scores/json/Games/{season}")
        resp.raise_for_status()
        return [e for raw in resp.json() if (e := self._map_to_event(raw))]

    async def fetch_odds(self, match_external_id: str) -> list:
        # Odds via SportsDataIO's odds endpoint
        resp = await self._client.get(f"odds/json/LiveGameOddsByGame/{match_external_id}")
        resp.raise_for_status()
        return resp.json()

    def _map_to_event(self, raw: dict) -> MatchEvent | None:
        """Map provider-specific JSON to unified MatchEvent schema."""
        try:
            return MatchEvent(
                external_id=str(raw["GameID"]),
                provider=self.provider_name,
                # ... map remaining fields
            )
        except (KeyError, ValueError):
            return None
```

**Repeat this pattern for every adapter.** Each adapter maps its provider's unique field names to the shared Pydantic schemas.

---

## G. Module 3 — Feature Engineering Pipeline

### G.1 Architecture

- Runs as a **PySpark Structured Streaming** job.
- Consumes from Kafka topics: `raw.match-events`, `raw.odds-updates`, `processed.sentiment`, `processed.biometric-features`.
- Writes computed features to:
  1. `feature_store` Postgres table (for model training).
  2. `processed.features` Kafka topic (for live model serving).

### G.2 Feature Definitions (Exhaustive)

Every feature MUST be registered in a YAML manifest:

```yaml
# services/feature_engine/configs/features.yaml

features:
  # --- Temporal ---
  - name: rolling_avg_goals_5
    description: "Mean goals scored over last 5 home/away matches"
    window: 5
    aggregation: mean
    column: goals_scored
    group_by: [team_id, venue_type]
    type: float

  - name: rolling_avg_goals_10
    description: "Mean goals scored over last 10 matches"
    window: 10
    aggregation: mean
    column: goals_scored
    group_by: [team_id]
    type: float

  - name: rolling_std_goals_5
    description: "Std dev of goals scored over last 5 matches"
    window: 5
    aggregation: std
    column: goals_scored
    group_by: [team_id]
    type: float

  - name: rolling_avg_xg_5
    description: "Mean expected goals (xG) over last 5 matches"
    window: 5
    aggregation: mean
    column: xg
    group_by: [team_id]
    type: float

  - name: rolling_avg_shots_on_target_5
    description: "Mean shots on target over last 5 matches"
    window: 5
    aggregation: mean
    column: shots_on_target
    group_by: [team_id]
    type: float

  - name: momentum_xg_slope_5
    description: "Linear regression slope of xG over last 5 matches"
    window: 5
    aggregation: linreg_slope
    column: xg
    group_by: [team_id]
    type: float

  - name: momentum_xg_slope_12
    description: "Linear regression slope of xG over last 12 matches"
    window: 12
    aggregation: linreg_slope
    column: xg
    group_by: [team_id]
    type: float

  - name: lag_1_goals
    description: "Goals scored in the previous match"
    lag: 1
    column: goals_scored
    group_by: [team_id]
    type: float

  - name: lag_2_goals
    description: "Goals scored two matches ago"
    lag: 2
    column: goals_scored
    group_by: [team_id]
    type: float

  - name: lag_3_goals
    description: "Goals scored three matches ago"
    lag: 3
    column: goals_scored
    group_by: [team_id]
    type: float

  # --- Schedule & Context ---
  - name: rest_days
    description: "Days since team's last match"
    type: int
    compute: date_diff

  - name: travel_distance_km
    description: "Approximate travel distance from last venue to current venue"
    type: float

  - name: is_home
    description: "1 if team is home, 0 if away"
    type: int

  - name: day_of_week
    description: "Day of week (0=Monday, 6=Sunday)"
    type: int

  # --- Market / Odds ---
  - name: opening_implied_prob_home
    description: "Implied probability of home win from the opening moneyline"
    type: float

  - name: closing_implied_prob_home
    description: "Implied probability of home win from the closing moneyline (ONLY for evaluation, NOT training)"
    type: float
    training_eligible: false  # DATA LEAKAGE GUARD

  - name: line_movement_spread
    description: "Change in spread from open to latest snapshot"
    type: float

  - name: cash_ticket_divergence
    description: "cash_pct_home - ticket_pct_home (positive = sharp on home)"
    type: float

  - name: reverse_line_movement
    description: "Boolean flag: line moved opposite to ticket majority"
    type: int

  # --- Biometric ---
  - name: team_avg_acwr
    description: "Mean ACWR of starting lineup"
    type: float

  - name: star_player_acwr
    description: "ACWR of the team's highest-rated player"
    type: float

  - name: team_avg_hrv
    description: "Mean HRV of starting lineup (most recent reading)"
    type: float

  - name: team_injury_risk_score
    description: "Aggregated injury risk probability across starters"
    type: float

  # --- Sentiment ---
  - name: team_sentiment_twitter_24h
    description: "Avg sentiment score from Twitter mentions in last 24 hours"
    type: float

  - name: team_sentiment_reddit_24h
    description: "Avg sentiment score from Reddit posts in last 24 hours"
    type: float

  - name: team_sentiment_news_24h
    description: "Avg sentiment score from news articles in last 24 hours"
    type: float

  - name: sentiment_volume_24h
    description: "Total number of sentiment-analyzed texts in last 24 hours"
    type: int
```

### G.3 Feature Implementation Rules

```
RULE-F1  Every feature computation function must take (team_id, match_datetime) and only query
         data WHERE recorded_at <= match_datetime.
RULE-F2  Use Spark window functions for rolling computations — never manually loop.
RULE-F3  Any feature marked `training_eligible: false` in the YAML must be excluded from
         training datasets by the data_loader.
RULE-F4  All null features default to the league-season median, NOT zero. Log every imputation.
RULE-F5  New features require: YAML registration + implementation + unit test + leakage test.
RULE-F6  Feature versioning: increment `version` in feature_store when feature set changes.
```

### G.4 Rolling Window Implementation Reference

```python
# services/feature_engine/src/temporal.py
from __future__ import annotations

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F


def add_rolling_avg(
    df: DataFrame,
    column: str,
    window_size: int,
    group_by: list[str],
    output_name: str,
) -> DataFrame:
    """Add a rolling average feature to the DataFrame.

    Args:
        df: Input Spark DataFrame, sorted by match date.
        column: Source column to average.
        window_size: Number of preceding rows to include.
        group_by: Partition columns (e.g., ['team_id']).
        output_name: Name of the new feature column.

    Returns:
        DataFrame with the new column appended.
    """
    window_spec = (
        Window.partitionBy(*group_by)
        .orderBy("match_datetime")
        .rowsBetween(-window_size, -1)  # ONLY past rows — no current row
    )
    return df.withColumn(output_name, F.avg(F.col(column)).over(window_spec))


def add_momentum_slope(
    df: DataFrame,
    column: str,
    window_size: int,
    group_by: list[str],
    output_name: str,
) -> DataFrame:
    """Add a linear regression slope feature (momentum indicator).

    Uses OLS slope = (n*sum(x*y) - sum(x)*sum(y)) / (n*sum(x^2) - sum(x)^2)
    where x = row number within window, y = column value.
    """
    window_spec = (
        Window.partitionBy(*group_by)
        .orderBy("match_datetime")
        .rowsBetween(-window_size, -1)
    )
    # Assign row numbers within window for x
    row_num_col = f"_rn_{output_name}"
    inner_window = (
        Window.partitionBy(*group_by)
        .orderBy("match_datetime")
    )
    df = df.withColumn(row_num_col, F.row_number().over(inner_window))

    n = window_size
    sum_x = F.sum(F.col(row_num_col)).over(window_spec)
    sum_y = F.sum(F.col(column)).over(window_spec)
    sum_xy = F.sum(F.col(row_num_col) * F.col(column)).over(window_spec)
    sum_x2 = F.sum(F.col(row_num_col) ** 2).over(window_spec)

    slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
    df = df.withColumn(output_name, slope)
    df = df.drop(row_num_col)
    return df
```

---

## H. Module 4 — ML Model Training & Registry

### H.1 Model Interface

Every model MUST implement this base class:

```python
# services/model_training/src/models/base_model.py
from __future__ import annotations

import abc
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class ModelMeta:
    name: str
    version: str
    hyperparameters: dict[str, Any]


class BaseModel(abc.ABC):
    """Abstract base for all prediction models."""

    meta: ModelMeta

    @abc.abstractmethod
    def train(self, X_train: pd.DataFrame, y_train: pd.Series) -> None:
        """Train the model on the provided data."""
        ...

    @abc.abstractmethod
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Return probability estimates. Shape: (n_samples, n_classes).
        Classes: [home_win, draw, away_win] for match-outcome models.
        """
        ...

    @abc.abstractmethod
    def save(self, path: Path) -> None:
        """Serialize model to disk."""
        ...

    @abc.abstractmethod
    def load(self, path: Path) -> None:
        """Deserialize model from disk."""
        ...

    def get_feature_importance(self) -> dict[str, float] | None:
        """Return feature importances if the model supports it."""
        return None
```

### H.2 Training Pipeline Rules

```
RULE-T1  All training runs are logged to MLflow: hyperparams, metrics, artifacts, tags.
RULE-T2  Hyperparameters are stored in YAML config files (one per model). Never hard-code.
RULE-T3  Data splits: CHRONOLOGICAL ONLY.
           - Training: all data before cutoff date.
           - Validation: next season / 20% of next chronological block.
           - Test: final held-out season (never used for tuning).
RULE-T4  Metrics to compute and log for EVERY run:
           - Accuracy
           - Brier score (primary)
           - Log-loss
           - F1 (macro)
           - ROI on value bets (backtest)
           - Calibration curve data (for reliability diagram)
RULE-T5  Model promotion: only models with Brier score < current production model's score
         get promoted via MLflow model registry (Staging → Production).
RULE-T6  Every model artifact includes a `feature_manifest.json` listing the exact features
         and their versions used for training. This enables reproducibility.
```

### H.3 Training Config Example

```yaml
# services/model_training/configs/xgboost.yaml
model:
  name: xgboost_match_outcome
  class: models.xgboost_model.XGBoostModel

hyperparameters:
  n_estimators: 800
  max_depth: 6
  learning_rate: 0.05
  subsample: 0.8
  colsample_bytree: 0.8
  min_child_weight: 5
  reg_alpha: 0.1
  reg_lambda: 1.0
  tree_method: gpu_hist    # Use GPU if available
  eval_metric: mlogloss

data:
  feature_version: "v1.2"
  target_column: match_result   # home_win | draw | away_win
  leagues: [premier_league, la_liga, serie_a, bundesliga, ligue_1]
  train_seasons: ["2021-22", "2022-23", "2023-24"]
  val_season: "2024-25"
  test_season: "2025-26"
  exclude_features:
    - closing_implied_prob_home   # leakage risk
```

### H.4 Training CLI

```bash
# Train a model
python -m src.train --config configs/xgboost.yaml

# Train ALL models sequentially
python -m src.train --config configs/*.yaml

# Promote a specific model run to staging
python -m src.registry --run-id <mlflow_run_id> --stage staging
```

### H.5 Poisson Model Reference Implementation

```python
# services/model_training/src/models/poisson.py
from __future__ import annotations

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

    def __init__(self, meta: ModelMeta) -> None:
        self.meta = meta
        self._attack: dict[str, float] = {}
        self._defense: dict[str, float] = {}
        self._home_advantage: float = 0.0
        self._simulations: int = meta.hyperparameters.get("simulations", 10_000)

    def train(self, X_train: pd.DataFrame, y_train: pd.Series) -> None:
        """Estimate attack/defense ratings via MLE."""
        # Implementation: maximize Poisson log-likelihood
        # over team attack and defense parameters
        teams = list(set(X_train["home_team"].tolist() + X_train["away_team"].tolist()))
        n_teams = len(teams)
        team_idx = {t: i for i, t in enumerate(teams)}

        def neg_log_likelihood(params: np.ndarray) -> float:
            attacks = params[:n_teams]
            defenses = params[n_teams:2 * n_teams]
            home_adv = params[-1]
            ll = 0.0
            for _, row in X_train.iterrows():
                hi = team_idx[row["home_team"]]
                ai = team_idx[row["away_team"]]
                lambda_home = np.exp(attacks[hi] + defenses[ai] + home_adv)
                lambda_away = np.exp(attacks[ai] + defenses[hi])
                ll += poisson.logpmf(row["home_score"], lambda_home)
                ll += poisson.logpmf(row["away_score"], lambda_away)
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

    def save(self, path: Path) -> None:
        import json
        data = {
            "attack": self._attack,
            "defense": self._defense,
            "home_advantage": self._home_advantage,
        }
        path.write_text(json.dumps(data))

    def load(self, path: Path) -> None:
        import json
        data = json.loads(path.read_text())
        self._attack = data["attack"]
        self._defense = data["defense"]
        self._home_advantage = data["home_advantage"]
```

---

## I. Module 5 — Biometric Integration Service

### I.1 ACWR Computation

```python
# services/biometric_service/src/acwr.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

ACUTE_WINDOW_DAYS = 7
CHRONIC_WINDOW_DAYS = 28
DANGER_ZONE_THRESHOLD = 1.5


def compute_acwr(
    workload_series: pd.DataFrame,
    as_of: datetime,
) -> float:
    """Compute the Acute:Chronic Workload Ratio.

    Args:
        workload_series: DataFrame with columns ['recorded_at', 'value'].
            'value' represents daily PlayerLoad or equivalent.
        as_of: The timestamp to compute the ratio for.

    Returns:
        ACWR ratio. Values > 1.5 indicate the 'danger zone'.
    """
    as_of_utc = as_of.astimezone(timezone.utc)
    acute_start = as_of_utc - timedelta(days=ACUTE_WINDOW_DAYS)
    chronic_start = as_of_utc - timedelta(days=CHRONIC_WINDOW_DAYS)

    acute_data = workload_series[
        (workload_series["recorded_at"] >= acute_start)
        & (workload_series["recorded_at"] <= as_of_utc)
    ]
    chronic_data = workload_series[
        (workload_series["recorded_at"] >= chronic_start)
        & (workload_series["recorded_at"] <= as_of_utc)
    ]

    acute_load = acute_data["value"].sum()
    chronic_avg = chronic_data["value"].sum() / (CHRONIC_WINDOW_DAYS / ACUTE_WINDOW_DAYS)

    if chronic_avg == 0:
        return 0.0

    return round(acute_load / chronic_avg, 4)


def is_danger_zone(acwr: float) -> bool:
    """Check if ACWR indicates injury risk."""
    return acwr >= DANGER_ZONE_THRESHOLD
```

### I.2 Injury Risk Classifier

```
REQUIREMENTS:
- Input features: ACWR (7/28), rolling HRV (7-day avg), resting HR trend,
  sleep quality score, gait symmetry index, cumulative PlayerLoad (season).
- Output: probability of injury in the next 7 days (float 0-1).
- Model: XGBoost classifier trained on historical injury records.
- Target accuracy: ≥ 85% (F1 macro on held-out test set).
- Log to MLflow as a separate experiment ("injury-risk").
```

---

## J. Module 6 — NLP & Sentiment Service

### J.1 Pipeline

```
[Scrapers] → [Preprocessing] → [BERT Inference] → [Score Aggregation] → [Kafka Publisher]
```

### J.2 Scraper Rules

```
RULE-N1  Twitter: Use official API v2 search/recent endpoint. Query: team name + league hashtags.
RULE-N2  Reddit: Use PRAW library. Subreddits: r/soccer, r/nfl, r/nba, r/baseball, r/hockey,
         r/fantasyfootball, r/sportsbook.
RULE-N3  News: Use RSS feeds from ESPN, BBC Sport, The Athletic, Bleacher Report.
RULE-N4  Scraping frequency: every 15 min for non-game-day, every 2 min during game windows.
RULE-N5  Store raw text in Kafka topic `raw.social-text` — never discard before classification.
RULE-N6  De-duplicate by content hash (SHA-256 of normalized text) before classification.
```

### J.3 Sentiment Classifier

```python
# services/nlp_service/src/classifier.py
from __future__ import annotations

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

MODEL_NAME = "nlptown/bert-base-multilingual-uncased-sentiment"  # Or fine-tuned sports model


class SentimentClassifier:
    """BERT-based sentiment classifier for sports text."""

    def __init__(self) -> None:
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        self.model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
        self.model.eval()

    def predict(self, texts: list[str]) -> list[float]:
        """Return sentiment scores in [-1.0, 1.0] for each text.

        -1.0 = very negative, 0.0 = neutral, 1.0 = very positive.
        """
        inputs = self.tokenizer(
            texts, padding=True, truncation=True, max_length=256, return_tensors="pt"
        )
        with torch.no_grad():
            outputs = self.model(**inputs)
        # Convert 5-star logits to [-1, 1]
        probs = torch.softmax(outputs.logits, dim=-1)
        stars = torch.arange(1, 6, dtype=torch.float32)
        weighted = (probs * stars).sum(dim=-1)
        normalized = (weighted - 3.0) / 2.0  # Map [1,5] → [-1,1]
        return normalized.tolist()
```

### J.4 News Event Detector

```
RULE-N7  Detect keywords: "ruled out", "injured", "doubtful", "suspended", "lineup change",
         "formation change", "manager sacked", "signing announced".
RULE-N8  On detection, publish a NewsAlert to Kafka topic `processed.news-alerts`.
RULE-N9  NewsAlerts trigger immediate feature re-computation for affected matches.
```

---

## K. Module 7 — Calibration & Betting Strategy Engine

### K.1 Calibration

```python
# services/model_serving/src/calibrator.py
from __future__ import annotations

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression


class ProbabilityCalibrator:
    """Post-hoc calibration using isotonic regression."""

    def __init__(self) -> None:
        self._calibrators: dict[int, IsotonicRegression] = {}

    def fit(self, raw_probs: np.ndarray, y_true: np.ndarray) -> None:
        """Fit one isotonic regressor per class.

        Args:
            raw_probs: Shape (n_samples, n_classes). Raw model probabilities.
            y_true: Shape (n_samples,). Integer class labels.
        """
        n_classes = raw_probs.shape[1]
        for c in range(n_classes):
            binary_target = (y_true == c).astype(int)
            iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
            iso.fit(raw_probs[:, c], binary_target)
            self._calibrators[c] = iso

    def calibrate(self, raw_probs: np.ndarray) -> np.ndarray:
        """Apply calibration and re-normalize to sum to 1."""
        calibrated = np.column_stack([
            self._calibrators[c].predict(raw_probs[:, c])
            for c in range(raw_probs.shape[1])
        ])
        row_sums = calibrated.sum(axis=1, keepdims=True)
        return calibrated / row_sums
```

### K.2 Kelly Criterion

```python
# libs/sports_common/utils/math.py

def kelly_fraction(
    prob_win: float,
    decimal_odds: float,
    fraction: float = 0.25,
) -> float:
    """Compute fractional Kelly stake.

    Args:
        prob_win: Model's estimated probability of winning.
        decimal_odds: Decimal odds offered by the book (e.g., 2.50).
        fraction: Kelly fraction to use (0.25 = quarter Kelly). Default conservative.

    Returns:
        Fraction of bankroll to wager. Returns 0.0 if no edge.
    """
    b = decimal_odds - 1.0
    q = 1.0 - prob_win
    edge = (b * prob_win - q) / b
    if edge <= 0:
        return 0.0
    return round(edge * fraction, 6)


def implied_probability(decimal_odds: float) -> float:
    """Convert decimal odds to implied probability."""
    return round(1.0 / decimal_odds, 6)


def remove_vig(home_odds: float, away_odds: float, draw_odds: float | None = None) -> tuple:
    """Remove vigorish to get true probabilities.

    Returns tuple of true probabilities (home, away[, draw]).
    """
    probs_raw = [1.0 / home_odds, 1.0 / away_odds]
    if draw_odds is not None:
        probs_raw.append(1.0 / draw_odds)
    total = sum(probs_raw)
    return tuple(round(p / total, 6) for p in probs_raw)


def brier_score(predicted_probs: list[float], actual_outcomes: list[int]) -> float:
    """Compute Brier score (lower is better).

    Args:
        predicted_probs: List of predicted probabilities for the positive class.
        actual_outcomes: List of 0/1 actual outcomes.
    """
    n = len(predicted_probs)
    return sum((p - a) ** 2 for p, a in zip(predicted_probs, actual_outcomes)) / n
```

### K.3 Value Bet Detection Rules

```
RULE-B1  A value bet exists when: model_prob > implied_prob + EDGE_THRESHOLD.
RULE-B2  Default EDGE_THRESHOLD = 0.03 (3%). Configurable per league.
RULE-B3  Never bet on events where model confidence interval (from calibration) overlaps zero edge.
RULE-B4  Track Closing Line Value (CLV) for every bet: if model_prob > closing_implied_prob,
         the bet had positive CLV regardless of outcome. This is the meta-metric for model quality.
RULE-B5  Max exposure per match = 5% of bankroll. Hard cap, regardless of Kelly output.
RULE-B6  Max daily exposure = 15% of bankroll.
```

---

## L. Module 8 — Explainability & Reporting Service

### L.1 SHAP Integration

```python
# services/model_serving/src/explainer.py
from __future__ import annotations

import shap
import numpy as np
import pandas as pd


class PredictionExplainer:
    """Generate SHAP explanations for model predictions."""

    def __init__(self, model: object, background_data: pd.DataFrame) -> None:
        """Initialize with a trained model and a background dataset for SHAP.

        Args:
            model: A trained model with a predict_proba method.
            background_data: A sample of ~100-500 rows from the training set.
        """
        self.explainer = shap.Explainer(model.predict_proba, background_data)

    def explain(self, X: pd.DataFrame) -> list[dict[str, float]]:
        """Compute SHAP values for each prediction.

        Returns list of dicts: [{"feature_name": shap_value, ...}, ...]
        """
        shap_values = self.explainer(X)
        results = []
        for i in range(len(X)):
            feature_shap = {
                col: round(float(shap_values.values[i, j, :].sum()), 6)
                for j, col in enumerate(X.columns)
            }
            # Sort by absolute impact
            sorted_shap = dict(
                sorted(feature_shap.items(), key=lambda x: abs(x[1]), reverse=True)
            )
            results.append(sorted_shap)
        return results
```

### L.2 Report Structure

```python
# services/reporting_service/src/report_builder.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class MatchResearchSnapshot:
    """Complete match report structure."""

    # Header
    match_id: str
    home_team: str
    away_team: str
    league: str
    scheduled_at: datetime
    generated_at: datetime

    # Section 1: Tactical Preview
    home_formation: str              # e.g., "4-3-3"
    away_formation: str
    home_press_intensity: str        # "high", "medium", "low"
    away_press_intensity: str
    home_buildup_style: str          # "short", "long", "mixed"
    away_buildup_style: str
    tactical_notes: str

    # Section 2: Biometric Status
    home_team_wellness: float        # 0-100 aggregated score
    away_team_wellness: float
    home_injury_risks: list[dict]    # [{"player": str, "acwr": float, "risk": str}]
    away_injury_risks: list[dict]

    # Section 3: Market Dynamics
    opening_spread: float
    current_spread: float
    line_movement_direction: str     # "toward_home", "toward_away", "stable"
    sharp_money_alert: bool
    cash_pct_home: float
    ticket_pct_home: float
    reverse_line_movement: bool

    # Section 4: Probabilistic Forecasts
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    predicted_home_score: float
    predicted_away_score: float
    score_distribution: dict         # {(0,0): 0.05, (1,0): 0.08, ...}

    # Section 5: Strategic Recommendations
    recommendations: list[dict]      # [{"selection": str, "confidence": str,
                                     #   "kelly_stake": float, "risk_tier": str}]

    # Section 6: SHAP Explanation
    positive_drivers: list[dict]     # [{"feature": str, "impact_pct": float}]
    negative_drivers: list[dict]
```

---

## M. Module 9 — Model Serving API

### M.1 Endpoints

```
GET  /health                        → HealthCheck
GET  /api/v1/predictions/{match_id} → MatchPrediction + SHAP
POST /api/v1/predictions/batch      → list[MatchPrediction]
WS   /ws/live/{match_id}            → Live streaming prediction updates
GET  /api/v1/value-bets             → Current value bets across all upcoming matches
GET  /api/v1/reports/{match_id}     → MatchResearchSnapshot (JSON)
GET  /api/v1/reports/{match_id}/pdf → PDF download
```

### M.2 Response Schema

```python
# Example: GET /api/v1/predictions/{match_id}
{
    "match_id": "uuid",
    "home_team": "Arsenal",
    "away_team": "Chelsea",
    "league": "premier_league",
    "scheduled_at": "2026-03-15T15:00:00Z",
    "model": "xgboost_match_outcome",
    "model_version": "v2.1",
    "probabilities": {
        "home_win": 0.5234,
        "draw": 0.2411,
        "away_win": 0.2355
    },
    "predicted_score": {
        "home": 1.78,
        "away": 1.12
    },
    "calibrated": true,
    "brier_score_trailing_100": 0.187,
    "value_bets": [
        {
            "selection": "home_win",
            "model_prob": 0.5234,
            "best_odds": 2.10,
            "implied_prob": 0.4762,
            "edge": 0.0472,
            "kelly_stake_pct": 1.85,
            "sportsbook": "DraftKings"
        }
    ],
    "shap_explanation": {
        "positive_drivers": [
            {"feature": "momentum_xg_slope_5", "impact": 0.082, "label": "Strong offensive form (+8.2%)"},
            {"feature": "is_home", "impact": 0.061, "label": "Home advantage (+6.1%)"}
        ],
        "negative_drivers": [
            {"feature": "star_player_acwr", "impact": -0.045, "label": "Key player fatigue risk (-4.5%)"},
            {"feature": "team_sentiment_twitter_24h", "impact": -0.021, "label": "Negative fan sentiment (-2.1%)"}
        ]
    },
    "generated_at": "2026-03-15T12:30:00Z"
}
```

### M.3 WebSocket Protocol

```
Client connects: ws://host/ws/live/{match_id}

Server sends JSON messages on every update:
{
    "type": "prediction_update",
    "match_id": "uuid",
    "minute": 37,
    "trigger": "goal_scored",  # What caused the recalculation
    "probabilities": { ... },
    "timestamp": "2026-03-15T15:37:12Z"
}
```

---

## N. Module 10 — Frontend Dashboard

### N.1 Tech Stack

```
Framework:     Next.js 14+ (App Router)
Language:      TypeScript (strict mode)
Styling:       Tailwind CSS + shadcn/ui components
Charts:        Recharts (line, bar, distribution) + custom SHAP waterfall
State:         React Query (TanStack Query) for server state
WebSocket:     Native WebSocket via custom hook
```

### N.2 Pages & Components Checklist

```
☐ Dashboard Home         — Today's matches with prediction summary cards
☐ Match Detail           — Full prediction breakdown + live updates via WS
☐ SHAP Waterfall Chart   — Visual decomposition of prediction drivers
☐ Line Movement Chart    — Opening → current spread timeline
☐ Biometric Gauges       — Player ACWR, HRV, wellness dials
☐ Sentiment Badge        — Team sentiment with volume indicator
☐ Value Bets Table       — Sortable table of current value-bet opportunities
☐ Reports Page           — List of generated reports, download as PDF
☐ Settings               — Configure Kelly fraction, edge threshold, leagues
```

---

## O. Infrastructure as Code

### O.1 Docker Compose (Local Development)

```yaml
# docker-compose.yml
version: "3.9"

services:
  zookeeper:
    image: confluentinc/cp-zookeeper:7.6.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181

  kafka:
    image: confluentinc/cp-kafka:7.6.0
    depends_on: [zookeeper]
    ports: ["9092:9092"]
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1

  postgres:
    image: postgres:16
    ports: ["5432:5432"]
    environment:
      POSTGRES_USER: sportspred
      POSTGRES_PASSWORD: sportspred
      POSTGRES_DB: sportspred
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  mlflow:
    image: ghcr.io/mlflow/mlflow:2.12.0
    ports: ["5000:5000"]
    command: mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri sqlite:///mlflow.db
    volumes:
      - mlflow_data:/mlflow

volumes:
  pgdata:
  mlflow_data:
```

### O.2 Kubernetes Deployment Template

```yaml
# infra/k8s/services/model-serving/deployment.yml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: model-serving
  namespace: sports-pred
spec:
  replicas: 2
  selector:
    matchLabels:
      app: model-serving
  template:
    metadata:
      labels:
        app: model-serving
    spec:
      containers:
        - name: model-serving
          image: registry.example.com/sports-pred/model-serving:latest
          ports:
            - containerPort: 8004
          envFrom:
            - secretRef:
                name: sports-pred-secrets
            - configMapRef:
                name: sports-pred-config
          resources:
            requests:
              cpu: "500m"
              memory: "1Gi"
            limits:
              cpu: "2000m"
              memory: "4Gi"
          readinessProbe:
            httpGet:
              path: /health
              port: 8004
            initialDelaySeconds: 10
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /health
              port: 8004
            initialDelaySeconds: 30
            periodSeconds: 10
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: model-serving-hpa
  namespace: sports-pred
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: model-serving
  minReplicas: 2
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

---

## P. CI/CD Pipeline

### P.1 GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml
name: CI

on:
  pull_request:
    branches: [develop, main]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test
        ports: ["5432:5432"]

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }

      - name: Install dependencies
        run: |
          pip install uv
          uv pip install -e "./libs[dev]"
          for svc in services/*/; do uv pip install -e "./$svc[dev]"; done

      - name: Lint
        run: ruff check .

      - name: Type-check
        run: mypy libs/ services/ --ignore-missing-imports

      - name: Test
        run: pytest --tb=short -q
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/test

      - name: Data leakage audit
        run: python -m pytest tests/ -k "leakage" -v
```

---

## Q. Testing Strategy

### Q.1 Test Categories

| Category | Location | What It Tests | Tool |
|:---|:---|:---|:---|
| **Unit** | `services/*/tests/test_*.py` | Individual functions in isolation | pytest |
| **Integration** | `services/*/tests/test_integration_*.py` | Service ↔ DB, Service ↔ Kafka | pytest + testcontainers |
| **Data Leakage** | `services/feature_engine/tests/test_leakage.py` | Every feature respects temporal boundaries | pytest (custom assertions) |
| **Model** | `services/model_training/tests/test_models.py` | Train/predict cycle, metric thresholds | pytest + MLflow |
| **API Contract** | `services/model_serving/tests/test_api.py` | Endpoint schemas, status codes | pytest + httpx |
| **E2E** | `tests/e2e/` | Full pipeline: ingest → feature → predict → report | pytest + docker-compose |

### Q.2 Data Leakage Test Example

```python
# services/feature_engine/tests/test_leakage.py
"""Data leakage tests — MUST pass before any model training."""
import pandas as pd
from sports_common.utils.data_guard import assert_no_leakage


def test_feature_timestamps_precede_match(feature_store_df: pd.DataFrame) -> None:
    """Assert every feature was computed before the match it predicts."""
    violations = feature_store_df[
        feature_store_df["computed_at"] > feature_store_df["match_scheduled_at"]
    ]
    assert len(violations) == 0, (
        f"DATA LEAKAGE: {len(violations)} features computed AFTER match time. "
        f"Sample match IDs: {violations['match_id'].head(5).tolist()}"
    )


def test_no_closing_line_in_training_features(training_df: pd.DataFrame) -> None:
    """Closing line must never appear in training features."""
    forbidden = ["closing_implied_prob_home", "closing_implied_prob_away"]
    present = [c for c in forbidden if c in training_df.columns]
    assert len(present) == 0, f"DATA LEAKAGE: forbidden features in training: {present}"
```

### Q.3 Minimum Test Coverage

```
RULE-QA1  Overall code coverage ≥ 80%.
RULE-QA2  Feature engineering functions: 100% coverage (every feature must have a test).
RULE-QA3  Data leakage tests: 100% coverage (every feature must have a temporal boundary test).
RULE-QA4  API endpoints: 100% coverage (every route/method combo must have a test).
RULE-QA5  Model wrappers: smoke tests for train → predict → save → load cycle.
```

---

## R. Coding Roadmap (Step-by-Step Build Order)

This is the exact order an AI agent should build the system. Each step should be completed, tested, and committed before moving to the next.

### Sprint 1 (Weeks 1–2): Foundation

```
STEP 01  Initialize Git repo with the folder structure from Section B.
STEP 02  Create `docker-compose.yml` (Section O.1). Run `docker-compose up -d`. Verify.
STEP 03  Build `libs/sports_common` package:
         - config.py (BaseSettings)
         - logging.py (structlog setup)
         - constants.py (enums)
         - schemas/*.py (ALL Pydantic models)
         - utils/math.py (Kelly, Brier, implied prob, remove vig)
         - utils/time.py
         - utils/data_guard.py
STEP 04  Create Alembic config. Write ALL migrations from Section D. Run `alembic upgrade head`.
STEP 05  Write `kafka_client.py` (producer + consumer wrappers). Test with Kafka.
STEP 06  Write unit tests for libs/. Target: 100% coverage.
```

### Sprint 2 (Weeks 3–4): Ingestion & Adapters

```
STEP 07  Build `base_adapter.py` (Section E.3).
STEP 08  Implement SportsDataIO adapter (Section F.2). Test with mock + live API.
STEP 09  Implement API-SPORTS adapter. Test.
STEP 10  Implement MySportsFeeds adapter. Test.
STEP 11  Implement Sportmonks adapter. Test.
STEP 12  Implement OddsJam adapter. Test.
STEP 13  Implement OpticOdds adapter. Test.
STEP 14  Build event validators (Section E.5). Test.
STEP 15  Build ingestion FastAPI app (main.py, health.py, consumers, producers).
STEP 16  Build `scripts/seed_db.py` — load 3+ seasons of historical data. Run it.
STEP 17  Integration test: adapter → Kafka → DB for each provider.
```

### Sprint 3 (Weeks 5–6): Feature Engineering

```
STEP 18  Write `features.yaml` manifest (Section G.2 — all features).
STEP 19  Implement `temporal.py` — rolling windows, lag, slope, IDW.
STEP 20  Implement `market.py` — implied prob, RLM, CLV, cash-ticket divergence.
STEP 21  Implement `biometric.py` — ACWR, team wellness aggregation.
STEP 22  Implement `sentiment.py` — aggregated sentiment scores.
STEP 23  Implement `store.py` — write features to Postgres + Kafka.
STEP 24  Build Spark job `main.py` that orchestrates the full pipeline.
STEP 25  Write data-leakage tests for EVERY feature (Section Q.2).
STEP 26  Backfill feature_store table for all historical seasons.
```

### Sprint 4 (Weeks 7–9): Model Training

```
STEP 27  Build `base_model.py` interface (Section H.1).
STEP 28  Implement `data_loader.py` — chronological splits, feature filtering.
STEP 29  Implement `evaluator.py` — Brier, accuracy, F1, log-loss, CLV.
STEP 30  Implement `registry.py` — MLflow logging + promotion.
STEP 31  Implement Poisson model (Section H.5). Train. Log to MLflow.
STEP 32  Implement Bayesian model. Train. Log.
STEP 33  Implement Random Forest model. Train. Log. Establish baseline metrics.
STEP 34  Implement XGBoost model. Train. Log. Compare to baseline.
STEP 35  Implement CNN module. Implement LSTM module. Combine into CNN-LSTM. Train. Log.
STEP 36  Implement Transformer model. Train. Log.
STEP 37  Implement TabNet model. Train. Log.
STEP 38  Compare all models in MLflow. Promote best to Staging.
```

### Sprint 5 (Weeks 8–9, parallel): Biometrics + NLP

```
STEP 39  Implement Catapult adapter (in ingestion service).
STEP 40  Implement WHOOP adapter (in ingestion service).
STEP 41  Build biometric_service: acwr.py, injury_risk.py, wellness.py, publisher.py.
STEP 42  Train injury-risk classifier. Log to MLflow.
STEP 43  Build NLP scrapers: twitter.py, reddit.py, news_rss.py.
STEP 44  Build preprocessing.py (tokenize, clean, POS tag).
STEP 45  Build classifier.py (BERT sentiment — Section J.3).
STEP 46  Build event_detector.py (breaking news alerts).
STEP 47  Build publisher.py (Kafka output).
STEP 48  Integration test: scrape → classify → Kafka → feature store.
```

### Sprint 6 (Weeks 10–11): Calibration & Serving

```
STEP 49  Build calibrator.py (Section K.1). Fit on validation set.
STEP 50  Build betting.py — value bet detection, Kelly staking.
STEP 51  Build explainer.py — SHAP integration (Section L.1).
STEP 52  Build cache.py — Redis prediction cache.
STEP 53  Build model_serving FastAPI app — all endpoints (Section M.1).
STEP 54  Implement WebSocket live updates (Section M.3).
STEP 55  API contract tests for every endpoint.
STEP 56  Run full chronological backtest (`scripts/backtest.py`).
STEP 57  Validate: Brier score ≤ 0.20 on test set.
```

### Sprint 7 (Weeks 11–12): Reporting & Frontend

```
STEP 58  Build report_builder.py — MatchResearchSnapshot assembly.
STEP 59  Build Jinja2 templates (HTML + Markdown).
STEP 60  Build pdf_exporter.py.
STEP 61  Reporting service FastAPI app + tests.
STEP 62  Initialize Next.js frontend (`create-next-app`).
STEP 63  Build Dashboard Home page + PredictionCard component.
STEP 64  Build Match Detail page + SHAP waterfall chart.
STEP 65  Build Line Movement Chart component.
STEP 66  Build Biometric Gauge + Sentiment Badge components.
STEP 67  Build Value Bets table page.
STEP 68  Build Reports page with PDF download.
STEP 69  Implement WebSocket hook for live updates.
STEP 70  Frontend tests (React Testing Library).
```

### Sprint 8 (Weeks 13–14): Deployment & Hardening

```
STEP 71  Write all Dockerfiles (Section O).
STEP 72  Write Kubernetes manifests for every service.
STEP 73  Write HPA configs.
STEP 74  Write CI/CD workflows (Section P.1).
STEP 75  Set up Prometheus exporters in each service.
STEP 76  Build Grafana dashboards (data quality, model drift, API latency).
STEP 77  Configure alerting (PagerDuty / Slack).
STEP 78  Implement automated retraining trigger (MLflow + cron).
STEP 79  Load test: 10× normal traffic simulation.
STEP 80  Chaos test: kill random pods, verify circuit breakers.
STEP 81  Security audit: API auth (JWT), rate limiting, CORS.
STEP 82  Final E2E test: full pipeline from live data → dashboard.
STEP 83  Deploy to staging. Smoke test.
STEP 84  Deploy to production. Monitor for 48 hours.
```

---

## S. Agent Workflow Protocol (MANDATORY)

This section defines how an AI agent MUST operate when building this project. The system uses **two files only**:

| File | Role | Agent Reads? | Agent Writes? |
|:---|:---|:---|:---|
| `AI Agent Coding Guide.md` | Immutable spec — rules, schemas, code, structure | YES (every session) | NO (never modify) |
| `PROGRESS.md` | Mutable state — tracks what's done, what's next, blockers, decisions | YES (every session) | YES (every step) |

### S.1 Session Start Protocol

Every time an agent session begins, it MUST execute this sequence:

```
1. READ  "AI Agent Coding Guide.md" — absorb all rules and context.
2. READ  "PROGRESS.md" — determine current state (last completed step, blockers, notes).
3. IDENTIFY the next uncompleted step from the checklist in PROGRESS.md.
4. EXECUTE that step, following the rules in this guide.
5. UPDATE PROGRESS.md immediately after completing the step.
6. REPEAT steps 3-5 until the session ends or the user intervenes.
```

### S.2 How to Update PROGRESS.md

After completing each step, the agent MUST update PROGRESS.md with:

```
1. Change the step's status checkbox from [ ] to [x].
2. Add a timestamped entry to the SESSION LOG at the bottom with:
   - What was done (files created/modified, commands run).
   - Any decisions made and WHY.
   - Any issues encountered and how they were resolved.
   - What the NEXT action should be if the session ends here.
```

### S.3 Rules for PROGRESS.md

```
RULE-P1  PROGRESS.md is the ONLY file the agent updates for tracking. No other tracking docs.
RULE-P2  Never delete previous session log entries — they form an audit trail.
RULE-P3  If a step is partially done, mark it with [~] and explain what remains in the log.
RULE-P4  If a step is BLOCKED, mark it with [!] and document the blocker.
RULE-P5  If a step required a deviation from the guide, document the deviation and rationale.
RULE-P6  Keep the session log concise — bullet points, not paragraphs.
RULE-P7  The agent must NEVER skip a step without marking it as skipped with justification.
RULE-P8  At session end, the last log entry must include "NEXT:" indicating the exact next action.
```

### S.4 Prompt Template for Starting a Session

Paste this to the agent at the start of every coding session:

```
You are building the Sports Prediction System.

WORKFLOW:
1. Read "AI Agent Coding Guide.md" — this is your immutable specification.
2. Read "PROGRESS.md" — this is your mutable state tracker.
3. Pick up where the last session left off.
4. After completing each step, update PROGRESS.md (check the box + add a session log entry).
5. Follow ALL rules in the guide (Sections A-Q). No exceptions.
6. If anything is ambiguous, default to the safer, more explicit option.
7. Write tests alongside implementation code.
8. Do not create extra markdown files for tracking — use PROGRESS.md only.

BEGIN.
```

---

*This document is the definitive coding specification. Any ambiguity should be resolved by defaulting to the safer, more explicit option.*
