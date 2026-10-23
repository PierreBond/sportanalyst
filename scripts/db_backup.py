"""Nightly Postgres backup to backups/*.sql.gz, keeping the last N dumps.

Prefers the local docker compose postgres service; falls back to a `pg_dump`
binary with DATABASE_URL_SYNC (for hosted DBs).
Optional: BACKUP_UPLOAD_CMD runs with the archive path appended (upstream copy).
"""
import gzip
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

KEEP = int(os.environ.get("DB_BACKUP_KEEP", "21"))
BACKUP_DIR = Path(os.environ.get("DB_BACKUP_DIR", "backups"))


def _dump_cmd() -> list[str]:
    compose = Path("docker-compose.deploy.yml")
    if compose.exists():
        return [
            "docker", "compose", "-f", str(compose), "exec", "-T", "postgres",
            "pg_dump", "-U", os.environ.get("POSTGRES_USER", "user"),
            "-d", os.environ.get("POSTGRES_DB", "sportspred"),
        ]
    url = (os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("no docker-compose.yml here and DATABASE_URL_SYNC unset")
    return ["pg_dump", "--dbname=" + url]


def main() -> int:
    BACKUP_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    out = BACKUP_DIR / f"sportspred_{ts}.sql.gz"
    with gzip.open(out, "wb", compresslevel=6) as f:
        subprocess.run(_dump_cmd(), stdout=f, check=True)
    size = out.stat().st_size
    if size < 1000:
        out.unlink()
        raise RuntimeError(f"pg_dump produced suspiciously small output ({size} bytes)")

    archives = sorted(BACKUP_DIR.glob("sportspred_*.sql.gz"))
    for old in archives[:-KEEP]:
        old.unlink()

    hook = os.environ.get("BACKUP_UPLOAD_CMD", "").strip()
    if hook:
        subprocess.run(f"{hook} {out}", shell=True, check=False)
        print(f"upload hook: {hook}")
    print(f"backup ok: {out} ({size / 1e6:.1f} MB), {min(len(archives), KEEP)} kept")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        from notify import notify
        notify("DB backup failed", str(e))
        print(f"backup failed: {e}", file=sys.stderr)
        sys.exit(1)
