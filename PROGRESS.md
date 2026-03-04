# PROGRESS.md — Sports Prediction System

> **Role:** This is the AI agent's mutable state file. The agent reads this at the start of every session to know where it left off, and updates it after every completed step.
>
> **Companion file:** `AI Agent Coding Guide.md` (immutable spec — never modify)
>
> **Last updated:** —

---

## Current Status

| Metric | Value |
|:---|:---|
| **Current Sprint** | Sprint 1 |
| **Current Step** | STEP 01 |
| **Steps Completed** | 0 / 84 |
| **Overall Progress** | 0% |
| **Blockers** | None |

---

## Step Checklist

Status legend:
- `[ ]` = Not started
- `[~]` = In progress / partially done
- `[x]` = Completed
- `[!]` = Blocked — see session log for details
- `[-]` = Skipped — see session log for justification

### Sprint 1 — Foundation (Weeks 1–2)

| Step | Status | Description | Guide Section |
|:---|:---|:---|:---|
| STEP 01 | [ ] | Initialize Git repo with the full folder structure | B |
| STEP 02 | [ ] | Create `docker-compose.yml`, run `docker-compose up -d`, verify | O.1 |
| STEP 03 | [ ] | Build `libs/sports_common` package (config, logging, constants, schemas, utils) | B, A, D |
| STEP 04 | [ ] | Create Alembic config, write ALL migrations, run `alembic upgrade head` | D |
| STEP 05 | [ ] | Write `kafka_client.py` (producer + consumer wrappers), test with Kafka | E.2 |
| STEP 06 | [ ] | Write unit tests for `libs/`. Target: 100% coverage | Q |

### Sprint 2 — Ingestion & Adapters (Weeks 3–4)

| Step | Status | Description | Guide Section |
|:---|:---|:---|:---|
| STEP 07 | [ ] | Build `base_adapter.py` abstract class | E.3 |
| STEP 08 | [ ] | Implement SportsDataIO adapter + tests | F.1, F.2 |
| STEP 09 | [ ] | Implement API-SPORTS adapter + tests | F.1 |
| STEP 10 | [ ] | Implement MySportsFeeds adapter + tests | F.1 |
| STEP 11 | [ ] | Implement Sportmonks adapter + tests | F.1 |
| STEP 12 | [ ] | Implement OddsJam adapter + tests | F.1 |
| STEP 13 | [ ] | Implement OpticOdds adapter + tests | F.1 |
| STEP 14 | [ ] | Build event validators + tests | E.5 |
| STEP 15 | [ ] | Build ingestion FastAPI app (main.py, health.py, consumers, producers) | E |
| STEP 16 | [ ] | Build `scripts/seed_db.py` — load 3+ seasons of historical data | C.2 |
| STEP 17 | [ ] | Integration test: adapter → Kafka → DB for each provider | Q.1 |

### Sprint 3 — Feature Engineering (Weeks 5–6)

| Step | Status | Description | Guide Section |
|:---|:---|:---|:---|
| STEP 18 | [ ] | Write `features.yaml` manifest (all features) | G.2 |
| STEP 19 | [ ] | Implement `temporal.py` — rolling windows, lag, slope, IDW | G.4 |
| STEP 20 | [ ] | Implement `market.py` — implied prob, RLM, CLV, cash-ticket divergence | G.2 |
| STEP 21 | [ ] | Implement `biometric.py` — ACWR, team wellness aggregation | G.2 |
| STEP 22 | [ ] | Implement `sentiment.py` — aggregated sentiment scores | G.2 |
| STEP 23 | [ ] | Implement `store.py` — write features to Postgres + Kafka | G.1 |
| STEP 24 | [ ] | Build Spark job `main.py` that orchestrates the full pipeline | G.1 |
| STEP 25 | [ ] | Write data-leakage tests for EVERY feature | Q.2, G.3 |
| STEP 26 | [ ] | Backfill feature_store table for all historical seasons | G |

### Sprint 4 — Model Training (Weeks 7–9)

| Step | Status | Description | Guide Section |
|:---|:---|:---|:---|
| STEP 27 | [ ] | Build `base_model.py` abstract interface | H.1 |
| STEP 28 | [ ] | Implement `data_loader.py` — chronological splits, feature filtering | H.2 |
| STEP 29 | [ ] | Implement `evaluator.py` — Brier, accuracy, F1, log-loss, CLV | H.2 |
| STEP 30 | [ ] | Implement `registry.py` — MLflow logging + promotion | H.2 |
| STEP 31 | [ ] | Implement Poisson model, train, log to MLflow | H.5 |
| STEP 32 | [ ] | Implement Bayesian model, train, log | H |
| STEP 33 | [ ] | Implement Random Forest model, train, log (establish baseline) | H |
| STEP 34 | [ ] | Implement XGBoost model, train, log, compare to baseline | H.3 |
| STEP 35 | [ ] | Implement CNN + LSTM + CNN-LSTM, train, log | H |
| STEP 36 | [ ] | Implement Transformer model, train, log | H |
| STEP 37 | [ ] | Implement TabNet model, train, log | H |
| STEP 38 | [ ] | Compare all models in MLflow, promote best to Staging | H.2 |

### Sprint 5 — Biometrics + NLP (Weeks 8–9, parallel)

| Step | Status | Description | Guide Section |
|:---|:---|:---|:---|
| STEP 39 | [ ] | Implement Catapult adapter (in ingestion service) | F.1 |
| STEP 40 | [ ] | Implement WHOOP adapter (in ingestion service) | F.1 |
| STEP 41 | [ ] | Build biometric_service: acwr.py, injury_risk.py, wellness.py, publisher.py | I |
| STEP 42 | [ ] | Train injury-risk classifier, log to MLflow | I.2 |
| STEP 43 | [ ] | Build NLP scrapers: twitter.py, reddit.py, news_rss.py | J.2 |
| STEP 44 | [ ] | Build preprocessing.py (tokenize, clean, POS tag) | J.1 |
| STEP 45 | [ ] | Build classifier.py (BERT sentiment) | J.3 |
| STEP 46 | [ ] | Build event_detector.py (breaking news alerts) | J.4 |
| STEP 47 | [ ] | Build publisher.py (Kafka output) | J |
| STEP 48 | [ ] | Integration test: scrape → classify → Kafka → feature store | Q.1 |

### Sprint 6 — Calibration & Serving (Weeks 10–11)

| Step | Status | Description | Guide Section |
|:---|:---|:---|:---|
| STEP 49 | [ ] | Build calibrator.py (isotonic regression), fit on validation set | K.1 |
| STEP 50 | [ ] | Build betting.py — value bet detection, Kelly staking | K.2, K.3 |
| STEP 51 | [ ] | Build explainer.py — SHAP integration | L.1 |
| STEP 52 | [ ] | Build cache.py — Redis prediction cache | M |
| STEP 53 | [ ] | Build model_serving FastAPI app — all endpoints | M.1 |
| STEP 54 | [ ] | Implement WebSocket live updates | M.3 |
| STEP 55 | [ ] | API contract tests for every endpoint | Q.1 |
| STEP 56 | [ ] | Run full chronological backtest (`scripts/backtest.py`) | K |
| STEP 57 | [ ] | Validate: Brier score ≤ 0.20 on test set | K |

### Sprint 7 — Reporting & Frontend (Weeks 11–12)

| Step | Status | Description | Guide Section |
|:---|:---|:---|:---|
| STEP 58 | [ ] | Build report_builder.py — MatchResearchSnapshot assembly | L.2 |
| STEP 59 | [ ] | Build Jinja2 templates (HTML + Markdown) | L |
| STEP 60 | [ ] | Build pdf_exporter.py | L |
| STEP 61 | [ ] | Reporting service FastAPI app + tests | L |
| STEP 62 | [ ] | Initialize Next.js frontend | N.1 |
| STEP 63 | [ ] | Build Dashboard Home page + PredictionCard component | N.2 |
| STEP 64 | [ ] | Build Match Detail page + SHAP waterfall chart | N.2 |
| STEP 65 | [ ] | Build Line Movement Chart component | N.2 |
| STEP 66 | [ ] | Build Biometric Gauge + Sentiment Badge components | N.2 |
| STEP 67 | [ ] | Build Value Bets table page | N.2 |
| STEP 68 | [ ] | Build Reports page with PDF download | N.2 |
| STEP 69 | [ ] | Implement WebSocket hook for live updates | N.2 |
| STEP 70 | [ ] | Frontend tests (React Testing Library) | Q |

### Sprint 8 — Deployment & Hardening (Weeks 13–14)

| Step | Status | Description | Guide Section |
|:---|:---|:---|:---|
| STEP 71 | [ ] | Write all Dockerfiles | O |
| STEP 72 | [ ] | Write Kubernetes manifests for every service | O.2 |
| STEP 73 | [ ] | Write HPA configs | O.2 |
| STEP 74 | [ ] | Write CI/CD workflows | P.1 |
| STEP 75 | [ ] | Set up Prometheus exporters in each service | O |
| STEP 76 | [ ] | Build Grafana dashboards (data quality, model drift, API latency) | O |
| STEP 77 | [ ] | Configure alerting (PagerDuty / Slack) | O |
| STEP 78 | [ ] | Implement automated retraining trigger (MLflow + cron) | O |
| STEP 79 | [ ] | Load test: 10x normal traffic simulation | Q |
| STEP 80 | [ ] | Chaos test: kill random pods, verify circuit breakers | Q |
| STEP 81 | [ ] | Security audit: API auth (JWT), rate limiting, CORS | M |
| STEP 82 | [ ] | Final E2E test: full pipeline from live data → dashboard | Q |
| STEP 83 | [ ] | Deploy to staging, smoke test | O |
| STEP 84 | [ ] | Deploy to production, monitor for 48 hours | O |

---

## Decisions Log

> Record every non-trivial decision the agent makes that deviates from or interprets the guide.

| # | Date | Step | Decision | Rationale |
|---|:---|:---|:---|:---|
| — | — | — | — | — |

---

## Known Issues & Blockers

> Track anything that prevents forward progress. Remove entries when resolved.

| # | Date | Step | Issue | Status | Resolution |
|---|:---|:---|:---|:---|:---|
| — | — | — | — | — | — |

---

## Session Log

> The agent appends a new entry here after EVERY session. Never delete previous entries.

### Template for Each Entry

```
#### Session [N] — [DATE]

**Steps completed this session:** STEP XX – STEP YY
**Duration context:** [short/medium/long session]

**Work done:**
- [ bullet points of files created, modified, commands run ]

**Decisions made:**
- [ any non-obvious choices and why ]

**Issues encountered:**
- [ problems and how they were resolved, or if still open ]

**NEXT:** [ exact next action for the following session ]
```

---

*(No sessions recorded yet — the first agent session will begin below this line.)*
