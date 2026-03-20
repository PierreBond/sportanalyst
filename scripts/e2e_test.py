from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from typing import Any

import httpx

from sports_common.logging import setup_logging, get_logger

setup_logging("e2e-test")
logger = get_logger(__name__)


class E2ETest:
    def __init__(self, base_url: str = "http://localhost:8004") -> None:
        self._base_url = base_url
        self._results: dict[str, Any] = {
            "started_at": datetime.now().isoformat(),
            "tests": [],
            "passed": 0,
            "failed": 0,
        }

    async def test_health_endpoint(self) -> dict[str, Any]:
        result = {"name": "health_endpoint", "passed": False, "details": {}}

        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=10.0) as client:
                response = await client.get("/health")

                result["details"]["status_code"] = response.status_code
                result["details"]["response"] = response.json()

                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "healthy":
                        result["passed"] = True

        except Exception as e:
            result["details"]["error"] = str(e)

        return result

    async def test_prediction_flow(self) -> dict[str, Any]:
        result = {"name": "prediction_flow", "passed": False, "details": {}}

        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=30.0) as client:
                response = await client.get("/api/v1/predictions/e2e-test-match")

                result["details"]["status_code"] = response.status_code

                if response.status_code == 200:
                    data = response.json()

                    required_fields = [
                        "match_id",
                        "home_team",
                        "away_team",
                        "probabilities",
                        "shap_explanation",
                    ]
                    missing = [f for f in required_fields if f not in data]
                    result["details"]["missing_fields"] = missing

                    if not missing:
                        result["passed"] = True

        except Exception as e:
            result["details"]["error"] = str(e)

        return result

    async def test_batch_prediction(self) -> dict[str, Any]:
        result = {"name": "batch_prediction", "passed": False, "details": {}}

        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=30.0) as client:
                payload = {
                    "matches": [
                        {"match_id": "e2e-1", "home_team": "Team A", "away_team": "Team B"},
                        {"match_id": "e2e-2", "home_team": "Team C", "away_team": "Team D"},
                    ]
                }

                response = await client.post("/api/v1/predictions/batch", json=payload)

                result["details"]["status_code"] = response.status_code

                if response.status_code == 200:
                    data = response.json()
                    result["details"]["num_predictions"] = len(data.get("predictions", []))

                    if len(data.get("predictions", [])) == 2:
                        result["passed"] = True

        except Exception as e:
            result["details"]["error"] = str(e)

        return result

    async def test_value_bets(self) -> dict[str, Any]:
        result = {"name": "value_bets", "passed": False, "details": {}}

        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=10.0) as client:
                response = await client.get("/api/v1/value-bets")

                result["details"]["status_code"] = response.status_code

                if response.status_code == 200:
                    data = response.json()
                    if "value_bets" in data:
                        result["passed"] = True

        except Exception as e:
            result["details"]["error"] = str(e)

        return result

    async def test_report_generation(self) -> dict[str, Any]:
        result = {"name": "report_generation", "passed": False, "details": {}}

        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=30.0) as client:
                response = await client.get("/api/v1/reports/e2e-test-match")

                result["details"]["status_code"] = response.status_code

                if response.status_code == 200:
                    data = response.json()

                    required_fields = [
                        "match_id",
                        "home_team",
                        "away_team",
                        "home_win_prob",
                        "draw_prob",
                        "away_win_prob",
                    ]
                    missing = [f for f in required_fields if f not in data]
                    result["details"]["missing_fields"] = missing

                    if not missing:
                        result["passed"] = True

        except Exception as e:
            result["details"]["error"] = str(e)

        return result

    async def test_models_endpoint(self) -> dict[str, Any]:
        result = {"name": "models_endpoint", "passed": False, "details": {}}

        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=10.0) as client:
                response = await client.get("/models")

                result["details"]["status_code"] = response.status_code

                if response.status_code == 200:
                    data = response.json()
                    if "models" in data and len(data["models"]) > 0:
                        result["passed"] = True

        except Exception as e:
            result["details"]["error"] = str(e)

        return result

    async def test_calibrator_fit(self) -> dict[str, Any]:
        result = {"name": "calibrator_fit", "passed": False, "details": {}}

        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=30.0) as client:
                payload = {
                    "probs": [
                        [0.5, 0.3, 0.2],
                        [0.4, 0.35, 0.25],
                        [0.6, 0.25, 0.15],
                    ],
                    "labels": [0, 1, 2],
                }

                response = await client.post("/models/calibrator/fit", json=payload)

                result["details"]["status_code"] = response.status_code

                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "success":
                        result["passed"] = True

        except Exception as e:
            result["details"]["error"] = str(e)

        return result

    async def run_all_tests(self) -> dict[str, Any]:
        logger.info("e2e_test_starting", base_url=self._base_url)

        tests = [
            self.test_health_endpoint,
            self.test_prediction_flow,
            self.test_batch_prediction,
            self.test_value_bets,
            self.test_report_generation,
            self.test_models_endpoint,
            self.test_calibrator_fit,
        ]

        for test in tests:
            result = await test()
            self._results["tests"].append(result)

            if result["passed"]:
                self._results["passed"] += 1
                logger.info("test_passed", test=result["name"])
            else:
                self._results["failed"] += 1
                logger.error("test_failed", test=result["name"], details=result["details"])

            await asyncio.sleep(0.5)

        self._results["completed_at"] = datetime.now().isoformat()
        self._results["pass_rate"] = round(
            self._results["passed"] / len(self._results["tests"]) * 100, 2
        )

        logger.info("e2e_test_complete", results=self._results)
        return self._results


async def main() -> None:
    parser = argparse.ArgumentParser(description="End-to-end test for sports prediction system")
    parser.add_argument(
        "--url",
        default="http://localhost:8004",
        help="Base URL of the API",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output JSON file for results",
    )

    args = parser.parse_args()

    tester = E2ETest(base_url=args.url)
    results = await tester.run_all_tests()

    print("\n" + "=" * 60)
    print("E2E TEST RESULTS")
    print("=" * 60)
    print(f"Total Tests:      {len(results['tests'])}")
    print(f"Passed:           {results['passed']}")
    print(f"Failed:          {results['failed']}")
    print(f"Pass Rate:        {results['pass_rate']}%")
    print("-" * 60)
    print("TEST DETAILS")
    print("-" * 60)

    for test in results["tests"]:
        status = "PASS" if test["passed"] else "FAIL"
        print(f"  {test['name']}: {status}")

    print("=" * 60 + "\n")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        logger.info("results_saved", path=args.output)


if __name__ == "__main__":
    asyncio.run(main())
