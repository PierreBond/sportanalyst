import asyncio
from pathlib import Path

import httpx


def parse_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()
    return data


async def main() -> None:
    root = Path(__file__).resolve().parents[1]
    fenv = parse_env(root / "frontend" / ".env.local")
    renv = parse_env(root / ".env")

    backend_key = fenv.get("BACKEND_API_KEY", "")
    public_key = fenv.get("NEXT_PUBLIC_API_KEY", "")
    api_url = fenv.get("NEXT_PUBLIC_API_URL", "http://127.0.0.1:8014")
    root_api_key = renv.get("API_KEY", "")
    db_url = renv.get("DATABASE_URL", "")

    print("=== ENV CHECK ===")
    print(f"frontend BACKEND_API_KEY set: {bool(backend_key)}")
    print(f"frontend NEXT_PUBLIC_API_KEY set: {bool(public_key)}")
    print(f"frontend NEXT_PUBLIC_API_URL: {api_url}")
    print(f"root API_KEY set: {bool(root_api_key)}")
    if backend_key and root_api_key:
        print(f"keys equal (BACKEND_API_KEY vs root API_KEY): {backend_key == root_api_key}")

    timeout = 20.0
    async with httpx.AsyncClient(timeout=timeout) as c:
        print("\n=== DIRECT HTTP CHECKS ===")

        try:
            r = await c.get("http://127.0.0.1:3000/api/backend/api/v1/matches/upcoming?limit=3")
            print(f"proxy /api/backend status: {r.status_code}")
            print(f"proxy body: {r.text[:260]}")
        except Exception as e:
            print(f"proxy call error: {type(e).__name__}: {str(e)[:180]}")

        try:
            r = await c.get("http://127.0.0.1:8014/health")
            print(f"backend /health status: {r.status_code}")
            print(f"backend /health body: {r.text[:140]}")
        except Exception as e:
            print(f"backend health error: {type(e).__name__}: {str(e)[:180]}")

        headers_f = {"X-API-Key": backend_key} if backend_key else {}
        try:
            r = await c.get("http://127.0.0.1:8014/api/v1/matches/upcoming?limit=3", headers=headers_f)
            print(f"backend upcoming with BACKEND_API_KEY status: {r.status_code}")
            print(f"backend upcoming body: {r.text[:260]}")
        except Exception as e:
            print(f"backend upcoming (frontend key) error: {type(e).__name__}: {str(e)[:180]}")

        headers_r = {"X-API-Key": root_api_key} if root_api_key else {}
        try:
            r = await c.get("http://127.0.0.1:8014/api/v1/matches/upcoming?limit=3", headers=headers_r)
            print(f"backend upcoming with root API_KEY status: {r.status_code}")
            print(f"backend upcoming body: {r.text[:260]}")
        except Exception as e:
            print(f"backend upcoming (root key) error: {type(e).__name__}: {str(e)[:180]}")

    print("\n=== DB FIXTURE CHECK ===")
    if not db_url:
        print("DATABASE_URL missing in root .env")
        return

    try:
        import asyncpg

        conn = await asyncpg.connect(db_url.replace("postgresql+asyncpg://", "postgresql://"))
        try:
            c_matches = await conn.fetchval("SELECT COUNT(*) FROM matches")
            c_teams = await conn.fetchval("SELECT COUNT(*) FROM teams")
            c_upcoming = await conn.fetchval(
                "SELECT COUNT(*) FROM matches WHERE scheduled_at >= NOW() - INTERVAL '1 day'"
            )
            sample = await conn.fetch(
                "SELECT match_id::text, league, scheduled_at "
                "FROM matches "
                "WHERE scheduled_at >= NOW() - INTERVAL '1 day' "
                "ORDER BY scheduled_at ASC LIMIT 3"
            )
            print(f"matches count: {c_matches}")
            print(f"teams count: {c_teams}")
            print(f"upcoming (>= now-1d) count: {c_upcoming}")
            print(f"sample upcoming rows: {[dict(r) for r in sample]}")
        finally:
            await conn.close()
    except Exception as e:
        print(f"db check error: {type(e).__name__}: {str(e)[:220]}")


if __name__ == "__main__":
    asyncio.run(main())
