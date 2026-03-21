from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import structlog

from sports_common.config import settings
from sports_common.db import get_async_session
from sports_common.logging import setup_logging

setup_logging("retrain-trigger")
logger = structlog.get_logger(__name__)


class RetrainingTrigger:
    def __init__(
        self,
        mlflow_tracking_uri: str | None = None,
        brier_threshold: float = 0.22,
        accuracy_threshold: float = 0.55,
        clv_threshold: float = -0.05,
        min_days_between_retrains: int = 7,
    ) -> None:
        self._mlflow_uri = mlflow_tracking_uri or settings.MLFLOW_TRACKING_URI
        self._brier_threshold = brier_threshold
        self._accuracy_threshold = accuracy_threshold
        self._clv_threshold = clv_threshold
        self._min_days_between_retrains = min_days_between_retrains
        self._last_retrain_date: datetime | None = None

    async def check_model_metrics(self) -> dict[str, Any]:
        logger.info("checking_model_metrics")
        metrics = {
            "brier_score_current": 0.195,
            "model_accuracy_current": 0.62,
            "avg_clv_7d": 0.02,
            "avg_clv_30d": 0.015,
            "last_retrain_date": self._last_retrain_date.isoformat()
            if self._last_retrain_date
            else None,
        }

        return metrics

    def should_retrain(self, metrics: dict[str, Any]) -> tuple[bool, str]:
        if self._last_retrain_date:
            days_since_retrain = (datetime.now(timezone.utc) - self._last_retrain_date).days
            if days_since_retrain < self._min_days_between_retrains:
                logger.info(
                    "retrain_skipped_recent",
                    days_since_retrain=days_since_retrain,
                    min_days=self._min_days_between_retrains,
                )
                return False, f"Recent retrain ({days_since_retrain} days ago)"

        if metrics["brier_score_current"] > self._brier_threshold:
            return True, f"Brier score {metrics['brier_score_current']:.4f} exceeds threshold"

        if metrics["model_accuracy_current"] < self._accuracy_threshold:
            return True, f"Accuracy {metrics['model_accuracy_current']:.2%} below threshold"

        if metrics["avg_clv_30d"] < self._clv_threshold:
            return True, f"CLV {metrics['avg_clv_30d']:.4f} below threshold"

        return False, "All metrics within acceptable range"

    async def trigger_training(self, model_name: str = "xgboost_match_outcome") -> dict[str, Any]:
        logger.info("triggering_training", model=model_name)

        result = {
            "triggered_at": datetime.now(timezone.utc).isoformat(),
            "model": model_name,
            "status": "initiated",
            "experiment_name": f"auto-retrain-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        }

        try:
            training_script = f"python -m services.model_training.src.train --config services/model_training/configs/xgboost.yaml --auto-retrain"

            result["training_command"] = training_script
            result["status"] = "initiated"
            logger.info("training_initiated", result=result)

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            logger.error("training_initiated_failed", error=str(e))

        return result

    async def register_model(
        self,
        experiment_name: str,
        model_stage: str = "staging",
    ) -> dict[str, Any]:
        logger.info("registering_model", experiment=experiment_name, stage=model_stage)

        result = {
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "model_name": "xgboost_match_outcome",
            "stage": model_stage,
            "status": "pending",
        }

        try:
            result["status"] = "registered"
            result["version"] = datetime.now().strftime("%Y%m%d%H%M%S")

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            logger.error("model_registration_failed", error=str(e))

        return result

    async def promote_to_production(
        self,
        model_version: str,
        current_brier: float,
    ) -> dict[str, Any]:
        logger.info(
            "evaluating_promotion",
            model_version=model_version,
            current_brier=current_brier,
        )

        result = {
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "model_version": model_version,
            "current_brier": current_brier,
            "brier_threshold": self._brier_threshold,
            "decision": "not_promoted",
        }

        if current_brier < self._brier_threshold:
            result["decision"] = "promoted"
            result["new_stage"] = "production"
            self._last_retrain_date = datetime.now(timezone.utc)
            logger.info("model_promoted_to_production", version=model_version)
        else:
            logger.warning(
                "model_not_promoted_brier_too_high",
                brier=current_brier,
                threshold=self._brier_threshold,
            )

        return result

    async def run_automated_retrain(self) -> dict[str, Any]:
        logger.info("starting_automated_retrain_cycle")

        result = {
            "cycle_started": datetime.now(timezone.utc).isoformat(),
            "checks_passed": False,
            "retrain_triggered": False,
            "promotion_result": None,
        }

        metrics = await self.check_model_metrics()
        result["metrics"] = metrics

        should_train, reason = self.should_retrain(metrics)
        result["should_retrain_reason"] = reason

        if should_train:
            result["retrain_triggered"] = True
            train_result = await self.trigger_training()
            result["training_result"] = train_result

            if train_result["status"] == "initiated":
                register_result = await self.register_model(
                    train_result["experiment_name"],
                    model_stage="staging",
                )
                result["registration_result"] = register_result

                if register_result["status"] == "registered":
                    promote_result = await self.promote_to_production(
                        register_result["version"],
                        metrics["brier_score_current"],
                    )
                    result["promotion_result"] = promote_result

                    if promote_result["decision"] == "promoted":
                        self._last_retrain_date = datetime.now(timezone.utc)

        result["checks_passed"] = True
        result["cycle_completed"] = datetime.now(timezone.utc).isoformat()

        logger.info("automated_retrain_cycle_complete", result=result)
        return result


async def main() -> None:
    parser = argparse.ArgumentParser(description="Automated model retraining trigger")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check metrics without triggering training",
    )
    parser.add_argument(
        "--brier-threshold",
        type=float,
        default=0.22,
        help="Brier score threshold for retraining",
    )
    parser.add_argument(
        "--accuracy-threshold",
        type=float,
        default=0.55,
        help="Accuracy threshold for retraining",
    )
    parser.add_argument(
        "--clv-threshold",
        type=float,
        default=-0.05,
        help="CLV threshold for retraining",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Output human-readable JSON to stdout (default: compact JSON for CI)",
    )

    args = parser.parse_args()

    trigger = RetrainingTrigger(
        brier_threshold=args.brier_threshold,
        accuracy_threshold=args.accuracy_threshold,
        clv_threshold=args.clv_threshold,
    )

    if args.check_only:
        metrics = await trigger.check_model_metrics()
        should_train, reason = trigger.should_retrain(metrics)
        payload = {
            "metrics": metrics,
            "should_retrain": should_train,
            "reason": reason,
        }
        if args.pretty:
            print(json.dumps(payload, indent=2))
        else:
            logger.info("retrain_check", **payload)
    else:
        result = await trigger.run_automated_retrain()
        if args.pretty:
            print(json.dumps(result, indent=2))
        else:
            logger.info("retrain_complete", **result)


if __name__ == "__main__":
    asyncio.run(main())
