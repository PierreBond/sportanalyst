"""Write predictions for upcoming fixtures into the predictions table.

This reuses the serving layer's own feature builder and model
(services/model_serving/src/main.py) instead of keeping a second copy of the
feature SQL, so the stored rows are exactly what the API serves.

A row is only replaced when it was written by a different model version:
within one model version the first prediction before kickoff is kept, which
is the one an honest forward test has to judge.
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "libs"))

from services.model_serving.src import main as ms  # noqa: E402

DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/sportspred"
)

UPCOMING_SQL = """
    SELECT m.match_id::text AS match_id
    FROM matches m
    WHERE (m.status IS NULL OR m.status = 'scheduled')
      AND m.scheduled_at >= NOW() - INTERVAL '1 day'
      AND m.scheduled_at < NOW() + INTERVAL '34 days'
    ORDER BY m.scheduled_at
"""

INSERT_SQL = """
    INSERT INTO predictions (prediction_id, match_id, model_name, model_version,
        predicted_at, home_win_prob, draw_prob, away_win_prob, is_live, created_at)
    VALUES (:pid, :mid, :mn, :mv, :now, :h, :d, :a, false, :now)
    ON CONFLICT (match_id) DO UPDATE SET
        prediction_id = EXCLUDED.prediction_id,
        model_name = EXCLUDED.model_name,
        model_version = EXCLUDED.model_version,
        predicted_at = EXCLUDED.predicted_at,
        home_win_prob = EXCLUDED.home_win_prob,
        draw_prob = EXCLUDED.draw_prob,
        away_win_prob = EXCLUDED.away_win_prob
    WHERE predictions.model_version IS DISTINCT FROM EXCLUDED.model_version
"""


async def run() -> None:
    engine = create_async_engine(DB_URL)
    async with ms.app.router.lifespan_context(ms.app):
        Session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with Session() as db:
            match_ids = list((await db.execute(text(UPCOMING_SQL))).scalars().all())
            model_version = ms._predictor.model_version
            model_name = ms._predictor.model_name
            now_dt = datetime.now(timezone.utc)

            written = 0
            for match_id in match_ids:
                payload = await ms._generate_prediction(match_id, db)
                probs = payload["probabilities"]
                await db.execute(
                    text(INSERT_SQL),
                    {
                        "pid": uuid4(),
                        "mid": match_id,
                        "mn": model_name,
                        "mv": model_version,
                        "now": now_dt,
                        "h": round(float(probs["home_win"]), 4),
                        "d": round(float(probs["draw"]), 4),
                        "a": round(float(probs["away_win"]), 4),
                    },
                )
                written += 1
            await db.commit()

    await engine.dispose()
    print(f"{written} predictions processed (model {model_version})")


if __name__ == "__main__":
    asyncio.run(run())
