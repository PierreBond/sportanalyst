from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent


def test_alembic_fails_without_database_url() -> None:
    """Alembic must fail with explicit error when DATABASE_URL_SYNC is unset."""
    env = os.environ.copy()
    env.pop("DATABASE_URL_SYNC", None)

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=REPO_ROOT / "alembic",
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode != 0, (
        f"Expected alembic to fail without DATABASE_URL_SYNC, got exit code {result.returncode}"
    )
    assert "DATABASE_URL_SYNC" in result.stderr or "RuntimeError" in result.stderr, (
        f"Expected explicit DATABASE_URL_SYNC error, got: {result.stderr}"
    )
    print(f"[PASS] alembic fails explicitly without DATABASE_URL_SYNC: {result.stderr[:120]}")


def test_nlp_classifier_import_smoke() -> None:
    """NLP classifier must import cleanly from project root."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from services.nlp_service.src.classifier import SentimentClassifier; print('ok')",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"NLP classifier import failed: {result.stderr}"
    assert "ok" in result.stdout, f"Unexpected output: {result.stdout}"
    print(f"[PASS] NLP classifier imports cleanly from project root")


def test_load_test_emits_line_delimited_json() -> None:
    """load_test.py must emit line-delimited JSON by default (CI path)."""
    result = subprocess.run(
        [
            sys.executable,
            "scripts/load_test.py",
            "--url",
            "http://localhost:9999",
            "--duration",
            "1",
            "--rps",
            "1",
            "--users",
            "1",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    stdout_lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
    parsed = []
    for line in stdout_lines:
        try:
            parsed.append(json.loads(line))
        except json.JSONDecodeError:
            pass

    assert len(parsed) > 0, f"No valid JSON lines found in stdout. Lines: {stdout_lines[:3]}"
    assert any("load_test" in str(p) for p in parsed), (
        f"Expected load_test key in structured output, got: {parsed}"
    )
    print(f"[PASS] load_test emits line-delimited JSON: {len(parsed)} lines parsed")


def test_e2e_test_emits_line_delimited_json() -> None:
    """e2e_test.py must emit line-delimited JSON by default (CI path)."""
    result = subprocess.run(
        [
            sys.executable,
            "scripts/e2e_test.py",
            "--url",
            "http://localhost:9999",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    stdout_lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
    parsed = []
    for line in stdout_lines:
        try:
            parsed.append(json.loads(line))
        except json.JSONDecodeError:
            pass

    assert len(parsed) > 0, f"No valid JSON lines found in stdout. Lines: {stdout_lines[:3]}"
    assert any("e2e_test" in str(p) for p in parsed), (
        f"Expected e2e_test key in structured output, got: {parsed}"
    )
    print(f"[PASS] e2e_test emits line-delimited JSON: {len(parsed)} lines parsed")


def test_math_docstrings_present() -> None:
    """All 13 math utility functions must have docstrings."""
    math_path = REPO_ROOT / "libs" / "sports_common" / "utils" / "math.py"
    source = math_path.read_text()

    functions = [
        "poisson_pmf",
        "poisson_cdf",
        "kelly_fraction",
        "fractional_kelly",
        "implied_probability",
        "remove_vigorish",
        "brier_score",
        "brier_score_multiclass",
        "log_loss",
        "expected_value",
        "closing_line_value",
        "calculate_roi",
        "simulate_bankroll",
    ]

    missing = []
    for fn in functions:
        pattern = f"def {fn}("
        idx = source.find(pattern)
        if idx == -1:
            missing.append(fn)
            continue
        next_def = source.find("\ndef ", idx + 1)
        snippet = source[idx : next_def if next_def != -1 else len(source)]
        if '"""' not in snippet and "'''" not in snippet:
            missing.append(fn)

    assert not missing, f"Functions missing docstrings: {missing}"
    print(f"[PASS] All {len(functions)} math functions have docstrings")


def test_config_no_hardcoded_credentials() -> None:
    """config.py must not have credentialed defaults for database_url."""
    config_path = REPO_ROOT / "libs" / "sports_common" / "config.py"
    source = config_path.read_text()

    assert "postgresql://user:pass" not in source, (
        "Hardcoded credentialed DB URL found in config.py"
    )
    print("[PASS] config.py has no hardcoded credentialed defaults")


if __name__ == "__main__":
    tests = [
        test_alembic_fails_without_database_url,
        test_nlp_classifier_import_smoke,
        test_load_test_emits_line_delimited_json,
        test_e2e_test_emits_line_delimited_json,
        test_math_docstrings_present,
        test_config_no_hardcoded_credentials,
    ]

    failed = []
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed.append(test.__name__)

    print(f"\n{'=' * 60}")
    if failed:
        print(f"FAILED: {len(failed)}/{len(tests)}")
        for name in failed:
            print(f"  - {name}")
        sys.exit(1)
    else:
        print(f"ALL PASSED: {len(tests)}/{len(tests)}")
