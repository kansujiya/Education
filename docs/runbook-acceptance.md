# v0.1 acceptance runbook

This is the **M-11 gate**: a fresh engineer who has never seen the project follows
this document from a blank laptop and reaches a green production smoke test in
**≤ 90 minutes** at **$0 infra spend**. If that fails, v0.1 is not done — fix
the docs.

## Pre-flight checklist (the volunteer prepares this off-the-clock)

- [ ] A laptop with `git`, `docker`, `uv`, `pnpm`, `node 20+` installed
- [ ] An SSH key (`ssh-keygen -t ed25519`)
- [ ] A free **Anthropic** account with the $5 signup credit
      ([console.anthropic.com](https://console.anthropic.com))

The accounts below are created **on the clock**:

- Oracle Cloud (Always-Free) — or Hetzner CX22 fallback (~€4.5/mo)
- Neon (Postgres + pgvector)
- Cloudflare (R2 + Pages)
- GitHub (this repo)

## The 90-minute clock

Time the volunteer with a stopwatch. The runbook is the canonical
[`tasks.md` Phase 10](../tasks.md). Tick each step as you go — every step has a
hard "done when" check. No skipping.

| Stage | Step (from `tasks.md` Phase 10) | Expected duration |
|------:|---------------------------------|-------------------|
| 1 | Generate SSH key + provision Oracle ARM VM (or Hetzner CX22) | 10 min |
| 2 | SSH in, install Docker + 4 GB swap + ufw | 5 min |
| 3 | Set up Neon project, run `CREATE EXTENSION vector` | 5 min |
| 4 | Set up Cloudflare R2 bucket + access tokens | 5 min |
| 5 | Get Anthropic key | 2 min |
| 6 | Clone repo on the VM, fill `.env`, `docker compose up -d` | 10 min |
| 7 | Run Alembic migrations, seed AWS CCP exam | 5 min |
| 8 | Wire Caddy + `*.nip.io` for free TLS | 5 min |
| 9 | Deploy web client to Cloudflare Pages | 5 min |
| 10 | Configure GitHub Actions deploy secrets, tag `v0.1.0-rc1` | 5 min |
| 11 | Add keep-alive cron, set Anthropic spend alert at $5 | 3 min |
| 12 | **Run `bash scripts/smoke-test.sh https://<vm-ip>.nip.io`** | 1 min |
| 13 | **Run `bash scripts/check-dashboards.sh`** | 5 min |

Total budget: ~66 min. The remaining 24 min absorb network slowness, Oracle
"out of capacity" retries (fall back to a different AZ or Hetzner), and reading.

## Acceptance gate

The volunteer fills in this row at the end:

```
Volunteer name: ___________________
Date:           ___________________
VM provider:    ___________________
Public URL:     https://__________
Smoke test:     [PASS] [FAIL]
Cost dashboards confirmed at $0:  [YES] [NO]
Time on the clock (start → green smoke):  __ : __
```

**v0.1 acceptance** = `Smoke test: PASS` AND `Cost dashboards confirmed at $0`
AND `time ≤ 90 minutes`. If any of those fails, raise a doc-bug PR before
declaring v0.1 done.

## What this gate proves

1. The deploy artefacts in `infra/`, `scripts/`, and `.github/workflows/` are
   complete enough that a stranger can use them without hand-holding.
2. The free-tier hosting choices in `tech-plan.md` §18 actually work end-to-end
   for the documented operator.
3. The product loop (signup → profile → cards → attempt → progress) survives a
   real network deployment, not just an in-process FastAPI test client.
4. Cost discipline: the Anthropic-only line item is budgeted, alerted, and
   capped per `tech-plan.md` §18.3.

## What's explicitly out of scope for the v0.1 gate

- Mobile build (M-1.1 work).
- Real Playwright e2e on the deployed web URL (a small subset of the
  vitest API-client suite stands in for now).
- Real-LLM evals (the deterministic eval fakes from M-3..M-5 lock the
  contract; real-LLM regression evals belong to v1.1).
- Live LLM observability (Langfuse self-host is documented in `tech-plan.md`
  §17 but not part of this 90-minute drill).

When any of those is the next bottleneck, raise it as a v1.1 milestone.
