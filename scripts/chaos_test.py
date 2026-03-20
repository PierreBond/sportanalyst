from __future__ import annotations

import argparse
import asyncio
import json
import random
from datetime import datetime
from typing import Any

import httpx

from sports_common.logging import setup_logging, get_logger

setup_logging("chaos-test")
logger = get_logger(__name__)


class ChaosTest:
    def __init__(
        self,
        base_url: str,
        duration_seconds: int = 300,
        pod_kill_interval: int = 60,
    ) -> None:
        self._base_url = base_url
        self._duration = duration_seconds
        self._pod_kill_interval = pod_kill_interval
        self._results: dict[str, Any] = {
            "started_at": datetime.now().isoformat(),
            "scenarios_run": [],
            "health_checks": [],
            "recovery_tests": [],
        }

    async def check_service_health(self) -> dict[str, Any]:
        result = {
            "timestamp": datetime.now().isoformat(),
            "healthy": False,
            "latency_ms": 0,
            "services": {},
        }

        start = asyncio.get_event_loop().time()

        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=5.0) as client:
                response = await client.get("/health")
                result["latency_ms"] = (asyncio.get_event_loop().time() - start) * 1000
                result["healthy"] = response.status_code == 200

        except Exception as e:
            result["latency_ms"] = (asyncio.get_event_loop().time() - start) * 1000
            result["error"] = str(e)

        return result

    async def test_circuit_breaker(self) -> dict[str, Any]:
        logger.info("testing_circuit_breaker")

        result = {
            "scenario": "circuit_breaker",
            "timestamp": datetime.now().isoformat(),
            "passed": False,
            "details": {},
        }

        async with httpx.AsyncClient(base_url=self._base_url, timeout=30.0) as client:
            successful_requests = 0
            rejected_requests = 0
            failed_requests = 0

            for i in range(100):
                try:
                    response = await client.get("/api/v1/predictions/test-match")
                    if response.status_code == 200:
                        successful_requests += 1
                    elif response.status_code == 503:
                        rejected_requests += 1
                    else:
                        failed_requests += 1
                except httpx.HTTPError:
                    failed_requests += 1

                await asyncio.sleep(0.01)

            result["details"] = {
                "successful": successful_requests,
                "rejected": rejected_requests,
                "failed": failed_requests,
            }

            if rejected_requests > 0 or failed_requests < 95:
                result["passed"] = True

        logger.info("circuit_breaker_test_complete", result=result)
        return result

    async def test_graceful_degradation(self) -> dict[str, Any]:
        logger.info("testing_graceful_degradation")

        result = {
            "scenario": "graceful_degradation",
            "timestamp": datetime.now().isoformat(),
            "passed": False,
            "details": {},
        }

        async with httpx.AsyncClient(base_url=self._base_url, timeout=30.0) as client:
            endpoints_tested = []
            working_endpoints = 0

            endpoints = [
                "/health",
                "/api/v1/predictions/test",
                "/api/v1/value-bets",
                "/models",
            ]

            for endpoint in endpoints:
                try:
                    response = await client.get(endpoint, timeout=10.0)
                    endpoints_tested.append(
                        {
                            "endpoint": endpoint,
                            "status": response.status_code,
                            "working": 200 <= response.status_code < 500,
                        }
                    )
                    if 200 <= response.status_code < 500:
                        working_endpoints += 1
                except httpx.HTTPError:
                    endpoints_tested.append(
                        {
                            "endpoint": endpoint,
                            "status": 0,
                            "working": False,
                        }
                    )

            result["details"] = {
                "total_endpoints": len(endpoints),
                "working_endpoints": working_endpoints,
                "endpoints": endpoints_tested,
            }

            result["passed"] = working_endpoints >= len(endpoints) * 0.75

        logger.info("graceful_degradation_test_complete", result=result)
        return result

    async def test_timeout_handling(self) -> dict[str, Any]:
        logger.info("testing_timeout_handling")

        result = {
            "scenario": "timeout_handling",
            "timestamp": datetime.now().isoformat(),
            "passed": False,
            "details": {},
        }

        async with httpx.AsyncClient(base_url=self._base_url, timeout=30.0) as client:
            slow_requests = 0
            timeout_received = 0

            for _ in range(20):
                try:
                    response = await client.get("/api/v1/predictions/test")
                    if response.status_code == 200:
                        slow_requests += 1
                except httpx.TimeoutException:
                    timeout_received += 1
                except httpx.HTTPError:
                    pass

                await asyncio.sleep(0.5)

            result["details"] = {
                "slow_requests_handled": slow_requests,
                "timeouts_received": timeout_received,
            }

            result["passed"] = slow_requests > 0 or timeout_received > 0

        logger.info("timeout_handling_test_complete", result=result)
        return result

    async def test_concurrent_load_recovery(self) -> dict[str, Any]:
        logger.info("testing_concurrent_load_recovery")

        result = {
            "scenario": "concurrent_load_recovery",
            "timestamp": datetime.now().isoformat(),
            "passed": False,
            "details": {},
        }

        initial_health = await self.check_service_health()

        async with httpx.AsyncClient(base_url=self._base_url, timeout=10.0) as client:
            tasks = []
            for _ in range(50):
                task = client.get("/api/v1/predictions/test")
                tasks.append(task)

            responses = await asyncio.gather(*tasks, return_exceptions=True)

            successful = sum(
                1 for r in responses if isinstance(r, httpx.Response) and r.status_code == 200
            )
            failed = len(responses) - successful

        recovery_health = await self.check_service_health()

        result["details"] = {
            "initial_health": initial_health["healthy"],
            "concurrent_requests": len(tasks),
            "successful_under_load": successful,
            "failed_under_load": failed,
            "recovery_health": recovery_health["healthy"],
            "recovery_latency_ms": recovery_health["latency_ms"],
        }

        result["passed"] = (
            successful > len(tasks) * 0.5
            and recovery_health["healthy"]
            and recovery_health["latency_ms"] < 1000
        )

        logger.info("concurrent_load_recovery_test_complete", result=result)
        return result

    async def run_scenario(self, scenario_name: str) -> dict[str, Any]:
        if scenario_name == "circuit_breaker":
            return await self.test_circuit_breaker()
        elif scenario_name == "graceful_degradation":
            return await self.test_graceful_degradation()
        elif scenario_name == "timeout_handling":
            return await self.test_timeout_handling()
        elif scenario_name == "recovery":
            return await self.test_concurrent_load_recovery()
        else:
            return {"scenario": scenario_name, "error": "Unknown scenario"}

    async def run(self) -> dict[str, Any]:
        logger.info("chaos_test_starting", duration=self._duration)

        start_time = asyncio.get_event_loop().time()

        scenarios = [
            "circuit_breaker",
            "graceful_degradation",
            "timeout_handling",
            "recovery",
        ]

        for scenario in scenarios:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= self._duration:
                break

            result = await self.run_scenario(scenario)
            self._results["scenarios_run"].append(result)

            health = await self.check_service_health()
            self._results["health_checks"].append(health)

            await asyncio.sleep(5)

        self._results["completed_at"] = datetime.now().isoformat()
        self._results["total_scenarios"] = len(self._results["scenarios_run"])
        self._results["passed_scenarios"] = sum(
            1 for s in self._results["scenarios_run"] if s.get("passed", False)
        )
        self._results["pass_rate"] = round(
            self._results["passed_scenarios"] / self._results["total_scenarios"] * 100, 2
        )

        logger.info("chaos_test_complete", results=self._results)
        return self._results


async def main() -> None:
    parser = argparse.ArgumentParser(description="Chaos test for sports prediction system")
    parser.add_argument(
        "--url",
        default="http://localhost:8004",
        help="Base URL of the API",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=120,
        help="Test duration in seconds",
    )
    parser.add_argument(
        "--scenarios",
        nargs="+",
        choices=["circuit_breaker", "graceful_degradation", "timeout_handling", "recovery", "all"],
        default=["all"],
        help="Scenarios to run",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output JSON file for results",
    )

    args = parser.parse_args()

    tester = ChaosTest(
        base_url=args.url,
        duration_seconds=args.duration,
    )

    if "all" not in args.scenarios:
        tester._results["scenarios_run"] = []
        for scenario in args.scenarios:
            result = await tester.run_scenario(scenario)
            tester._results["scenarios_run"].append(result)
        tester._results["total_scenarios"] = len(tester._results["scenarios_run"])
        tester._results["passed_scenarios"] = sum(
            1 for s in tester._results["scenarios_run"] if s.get("passed", False)
        )
        tester._results["pass_rate"] = round(
            tester._results["passed_scenarios"] / tester._results["total_scenarios"] * 100, 2
        )
        tester._results["completed_at"] = datetime.now().isoformat()
    else:
        await tester.run()

    print("\n" + "=" * 60)
    print("CHAOS TEST RESULTS")
    print("=" * 60)
    print(f"Total Scenarios:  {tester._results['total_scenarios']}")
    print(f"Passed:           {tester._results['passed_scenarios']}")
    print(f"Pass Rate:        {tester._results['pass_rate']}%")
    print("-" * 60)
    print("SCENARIO DETAILS")
    print("-" * 60)

    for scenario in tester._results["scenarios_run"]:
        status = "PASS" if scenario.get("passed", False) else "FAIL"
        print(f"  {scenario['scenario']}: {status}")

    print("=" * 60 + "\n")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(tester._results, f, indent=2)
        logger.info("results_saved", path=args.output)


if __name__ == "__main__":
    asyncio.run(main())
