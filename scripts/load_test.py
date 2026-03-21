from __future__ import annotations

import argparse
import asyncio
import json
import random
import time
from datetime import datetime
from typing import Any

import httpx

from sports_common.logging import setup_logging, get_logger

setup_logging("load-test")
logger = get_logger(__name__)


class LoadTest:
    def __init__(
        self,
        base_url: str,
        duration_seconds: int = 300,
        target_rps: int = 100,
        num_users: int = 50,
    ) -> None:
        self._base_url = base_url
        self._duration = duration_seconds
        self._target_rps = target_rps
        self._num_users = num_users
        self._results: dict[str, Any] = {
            "started_at": datetime.now().isoformat(),
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "status_codes": {},
            "latencies": [],
            "errors": [],
        }

    async def make_request(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        method: str = "GET",
    ) -> dict[str, Any]:
        start_time = time.perf_counter()
        result = {
            "endpoint": endpoint,
            "method": method,
            "success": False,
            "status_code": 0,
            "latency_ms": 0,
            "error": None,
        }

        try:
            if method == "GET":
                response = await client.get(endpoint, timeout=30.0)
            elif method == "POST":
                response = await client.post(endpoint, json={}, timeout=30.0)
            else:
                response = await client.request(method, endpoint, timeout=30.0)

            result["status_code"] = response.status_code
            result["latency_ms"] = (time.perf_counter() - start_time) * 1000
            result["success"] = 200 <= response.status_code < 300

        except httpx.TimeoutException:
            result["error"] = "timeout"
            result["latency_ms"] = 30000
        except httpx.HTTPError as e:
            result["error"] = str(e)
            result["latency_ms"] = (time.perf_counter() - start_time) * 1000
        except Exception as e:
            result["error"] = str(e)
            result["latency_ms"] = (time.perf_counter() - start_time) * 1000

        return result

    async def simulate_user(
        self,
        user_id: int,
        endpoints: list[str],
        requests_per_user: int,
    ) -> list[dict[str, Any]]:
        results = []
        async with httpx.AsyncClient(base_url=self._base_url) as client:
            for i in range(requests_per_user):
                endpoint = random.choice(endpoints)
                result = await self.make_request(client, endpoint)
                result["user_id"] = user_id
                result["request_num"] = i
                results.append(result)

                await asyncio.sleep(random.uniform(0.01, 0.1))

        return results

    async def run(self) -> dict[str, Any]:
        logger.info(
            "load_test_starting",
            duration=self._duration,
            target_rps=self._target_rps,
            num_users=self._num_users,
        )

        endpoints = [
            "/health",
            "/api/v1/predictions/match-123",
            "/api/v1/predictions/match-456",
            "/api/v1/value-bets",
            "/api/v1/reports/match-123",
            "/models",
        ]

        requests_per_user = (self._target_rps * self._duration) // self._num_users

        start_time = time.time()
        tasks = []

        for user_id in range(self._num_users):
            task = asyncio.create_task(self.simulate_user(user_id, endpoints, requests_per_user))
            tasks.append(task)

            await asyncio.sleep(self._duration / self._num_users)

        logger.info("all_users_started", num_tasks=len(tasks))

        all_results = []
        for task in asyncio.as_completed(tasks):
            results = await task
            all_results.extend(results)

        elapsed = time.time() - start_time

        for result in all_results:
            self._results["total_requests"] += 1
            if result["success"]:
                self._results["successful_requests"] += 1
            else:
                self._results["failed_requests"] += 1

            status = str(result["status_code"])
            self._results["status_codes"][status] = self._results["status_codes"].get(status, 0) + 1

            self._results["latencies"].append(result["latency_ms"])

            if result["error"]:
                self._results["errors"].append(
                    {
                        "endpoint": result["endpoint"],
                        "error": result["error"],
                    }
                )

        self._results["completed_at"] = datetime.now().isoformat()
        self._results["elapsed_seconds"] = round(elapsed, 2)
        self._results["actual_rps"] = round(self._results["total_requests"] / elapsed, 2)
        self._results["success_rate"] = round(
            self._results["successful_requests"] / self._results["total_requests"] * 100, 2
        )

        if self._results["latencies"]:
            sorted_latencies = sorted(self._results["latencies"])
            self._results["latency_p50"] = round(sorted_latencies[len(sorted_latencies) // 2], 2)
            self._results["latency_p95"] = round(
                sorted_latencies[int(len(sorted_latencies) * 0.95)], 2
            )
            self._results["latency_p99"] = round(
                sorted_latencies[int(len(sorted_latencies) * 0.99)], 2
            )
            self._results["latency_avg"] = round(
                sum(self._results["latencies"]) / len(self._results["latencies"]), 2
            )
            self._results["latency_max"] = round(max(self._results["latencies"]), 2)

        del self._results["latencies"]

        logger.info("load_test_complete", results=self._results)
        return self._results


async def main() -> None:
    parser = argparse.ArgumentParser(description="Load test for sports prediction API")
    parser.add_argument(
        "--url",
        default="http://localhost:8004",
        help="Base URL of the API",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Test duration in seconds",
    )
    parser.add_argument(
        "--rps",
        type=int,
        default=100,
        help="Target requests per second",
    )
    parser.add_argument(
        "--users",
        type=int,
        default=50,
        help="Number of concurrent users",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output JSON file for results",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Print human-readable summary to stdout (default: CI mode emits structured logs)",
    )

    args = parser.parse_args()

    tester = LoadTest(
        base_url=args.url,
        duration_seconds=args.duration,
        target_rps=args.rps,
        num_users=args.users,
    )

    results = await tester.run()

    if args.pretty:
        print("\n" + "=" * 60)
        print("LOAD TEST RESULTS")
        print("=" * 60)
        print(f"Duration:        {results['elapsed_seconds']}s")
        print(f"Total Requests:  {results['total_requests']}")
        print(f"Successful:      {results['successful_requests']}")
        print(f"Failed:          {results['failed_requests']}")
        print(f"Success Rate:    {results['success_rate']}%")
        print(f"Actual RPS:      {results['actual_rps']}")
        print("-" * 60)
        print("LATENCY")
        print("-" * 60)
        print(f"Average:         {results.get('latency_avg', 'N/A')}ms")
        print(f"p50:             {results.get('latency_p50', 'N/A')}ms")
        print(f"p95:             {results.get('latency_p95', 'N/A')}ms")
        print(f"p99:             {results.get('latency_p99', 'N/A')}ms")
        print(f"Max:             {results.get('latency_max', 'N/A')}ms")
        print("=" * 60 + "\n")
    else:
        logger.info(
            "load_test_summary",
            elapsed_seconds=results["elapsed_seconds"],
            total_requests=results["total_requests"],
            successful_requests=results["successful_requests"],
            failed_requests=results["failed_requests"],
            success_rate=results["success_rate"],
            actual_rps=results["actual_rps"],
            latency_avg=results.get("latency_avg"),
            latency_p50=results.get("latency_p50"),
            latency_p95=results.get("latency_p95"),
            latency_p99=results.get("latency_p99"),
            latency_max=results.get("latency_max"),
        )

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        logger.info("results_saved", path=args.output)


if __name__ == "__main__":
    asyncio.run(main())
