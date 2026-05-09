"""M-10 load test.

Spins up N virtual users that walk the full journey concurrently:
  signup → profile → cards → attempt x M.

Reports request count, success rate, and p50 / p95 latency for each
endpoint. Pure Python + httpx, runs against any base URL.

Usage:
    uv run python scripts/loadtest.py --base-url http://localhost:8000 --users 10 --attempts 5
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from secrets import token_hex
from typing import Any

import httpx


async def _journey(
    client: httpx.AsyncClient,
    user_idx: int,
    attempts: int,
    timings: dict[str, list[float]],
    failures: dict[str, int],
) -> None:
    email = f"load_{token_hex(4)}@example.com"
    password = "loadtest-pw-" + token_hex(8)
    exam_date = (datetime.now(UTC) + timedelta(days=60)).isoformat()

    async def _step(name: str, coro: Any) -> Any:
        start = time.perf_counter()
        try:
            res = await coro
            res.raise_for_status()
            timings[name].append(time.perf_counter() - start)
            return res
        except Exception:
            failures[name] += 1
            raise

    res = await _step(
        "signup",
        client.post("/v1/auth/signup", json={"email": email, "password": password}),
    )
    token = res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    await _step(
        "profile",
        client.post(
            "/v1/me/profile",
            headers=headers,
            json={
                "exam_id": "aws-ccp",
                "exam_date": exam_date,
                "daily_minutes": 60,
                "language": "en",
            },
        ),
    )
    res = await _step(
        "cards",
        client.post("/v1/me/topics/cloud-concepts.benefits/cards", headers=headers),
    )
    card_ids = [c["id"] for c in res.json()["cards"]]

    for i in range(min(attempts, len(card_ids))):
        await _step(
            "attempt",
            client.post(
                f"/v1/me/cards/{card_ids[i]}/attempt",
                headers=headers,
                json={"answer": "I clearly mention pay-as-you-go in my answer."},
            ),
        )

    await _step("progress", client.get("/v1/me/progress", headers=headers))
    _ = user_idx  # used only for log noise


def _summarise(
    timings: dict[str, list[float]], failures: dict[str, int]
) -> tuple[bool, list[tuple[str, int, int, float, float]]]:
    rows: list[tuple[str, int, int, float, float]] = []
    p95_ok = True
    for name, samples in timings.items():
        n = len(samples)
        f = failures.get(name, 0)
        if not samples:
            rows.append((name, n, f, 0.0, 0.0))
            continue
        samples.sort()
        p50 = samples[len(samples) // 2]
        p95 = samples[max(0, int(len(samples) * 0.95) - 1)]
        rows.append((name, n, f, p50, p95))
        if p95 > 5.0:
            p95_ok = False
    rows.sort()
    return p95_ok, rows


async def _run(base_url: str, users: int, attempts: int) -> int:
    timings: dict[str, list[float]] = defaultdict(list)
    failures: dict[str, int] = defaultdict(int)
    print(f"Load test: {users} users x {attempts} attempts → {base_url}")

    async with httpx.AsyncClient(base_url=base_url, timeout=20.0) as client:
        await asyncio.gather(
            *(_journey(client, i, attempts, timings, failures) for i in range(users)),
            return_exceptions=True,
        )

    p95_ok, rows = _summarise(timings, failures)
    print(f"\n{'endpoint':<10} {'count':>7} {'fail':>6} {'p50 (s)':>10} {'p95 (s)':>10}")
    for name, n, f, p50, p95 in rows:
        print(f"{name:<10} {n:>7} {f:>6} {p50:>10.3f} {p95:>10.3f}")

    total_failures = sum(failures.values())
    print(
        f"\nFailures: {total_failures} / {sum(len(v) for v in timings.values()) + total_failures}"
    )
    if total_failures > 0:
        print("\033[31m✗ Some requests failed.\033[0m")
        return 1
    if not p95_ok:
        print("\033[33m⚠ p95 latency exceeded 5s on at least one endpoint.\033[0m")
        return 2
    print(
        f"\033[32m✓ Load test passed — p95 < 5s on every endpoint, "
        f"mean ≈ {statistics.mean(rows[0][3:5]):.3f}s.\033[0m"
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--users", type=int, default=10)
    parser.add_argument("--attempts", type=int, default=5)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args.base_url, args.users, args.attempts)))


if __name__ == "__main__":
    main()
