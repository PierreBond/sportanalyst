#!/usr/bin/env python3
import asyncio
import httpx
import sys

async def main():
    print("Testing cache resilience with Redis unavailable...")
    print("-" * 60)
    
    base_url = "http://127.0.0.1:8013"
    headers = {"X-API-Key": "test-key-12345"}
    timeout = 30.0  # Increased timeout to handle slow endpoints
    
    tests_passed = 0
    tests_failed = 0
    
    async with httpx.AsyncClient() as client:
        # Test prediction endpoint
        print("\n1. Testing GET /api/v1/predictions/live-001")
        try:
            response = await client.get(
                base_url + "/api/v1/predictions/live-001",
                headers=headers,
                timeout=timeout
            )
            status = response.status_code
            print(f"   Status: {status}")
            if status == 200:
                print("   OK: Returns 200")
                tests_passed += 1
            else:
                print(f"   FAIL: Expected 200, got {status}")
                print(f"   Body: {response.text[:200]}")
                tests_failed += 1
        except httpx.TimeoutException as e:
            print(f"   TIMEOUT: Request took too long")
            tests_failed += 1
        except Exception as e:
            print(f"   FAIL: {type(e).__name__}: {str(e)[:100]}")
            tests_failed += 1
        
        # Test value bets endpoint
        print("\n2. Testing GET /api/v1/value-bets")
        try:
            response = await client.get(
                base_url + "/api/v1/value-bets?min_edge=0.02",
                headers=headers,
                timeout=timeout
            )
            status = response.status_code
            print(f"   Status: {status}")
            if status == 200:
                print("   OK: Returns 200")
                tests_passed += 1
            else:
                print(f"   FAIL: Expected 200, got {status}")
                tests_failed += 1
        except httpx.TimeoutException as e:
            print(f"   TIMEOUT: Request took too long")
            tests_failed += 1
        except Exception as e:
            print(f"   FAIL: {type(e).__name__}: {str(e)[:100]}")
            tests_failed += 1
        
        # Test matches endpoint
        print("\n3. Testing GET /api/v1/matches/upcoming")
        try:
            response = await client.get(
                base_url + "/api/v1/matches/upcoming?limit=8",
                headers=headers,
                timeout=timeout
            )
            status = response.status_code
            print(f"   Status: {status}")
            if status == 200:
                print("   OK: Returns 200")
                tests_passed += 1
            else:
                print(f"   FAIL: Expected 200, got {status}")
                tests_failed += 1
        except httpx.TimeoutException as e:
            print(f"   TIMEOUT: Request took too long")
            tests_failed += 1
        except Exception as e:
            print(f"   FAIL: {type(e).__name__}: {str(e)[:100]}")
            tests_failed += 1
    
    print("\n" + "-" * 60)
    print(f"Results: {tests_passed} passed, {tests_failed} failed")
    
    if tests_failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())

