# Education AI

An agentic AI exam-preparation companion. Multi-agent system that takes a candidate from "I have an exam on date X" to "I am ready to clear it."

> **Status:** v0.1 complete (M-0 → M-11). 139 Python tests + 10 web tests green;
> mypy strict over 68 source files; ruff clean. See [`milestones.md`](./milestones.md)
> for the full ladder.

## Documentation

| Doc | What it covers |
|-----|----------------|
| [`prd.md`](./prd.md) | Product requirements, personas, journey, FRs |
| [`tech-plan.md`](./tech-plan.md) | Architecture, agents, A2A/MCP/RAG, frameworks, deployment, free-tier hosting |
| [`tasks.md`](./tasks.md) | Build runbook with step-by-step deployment guide |
| [`backlog.md`](./backlog.md) | 109 ticket-sized work items across 14 epics |
| [`milestones.md`](./milestones.md) | 11 vertical-slice milestones, each demoable + tested |

## Quickstart

Prerequisites: `uv` ≥ 0.8, Docker, an Anthropic API key.

```bash
git clone <this-repo>
cd Education
cp .env.example .env
# edit .env: set ANTHROPIC_API_KEY=sk-ant-...

make install        # uv sync --all-packages --extra dev
make dev            # docker compose: postgres, redis, minio, langfuse
```

### M-0 demo · "Hello, agent"

```bash
make demo           # streams a Claude response to your terminal
```

A second identical run shows a high prompt-cache hit ratio reported by `edu ask --no-stream "..."`.

### M-1 demo · "Syllabus loader"

```bash
make seed           # applies migrations, calls mcp-syllabus, prints the topic tree
```

The `seed` target runs Alembic, then loads the AWS CCP exam syllabus through the `mcp-syllabus` MCP server (spawned over stdio), and renders the topic tree to stdout.

### M-2 demo · "Tutor + mind map, streamed"

```bash
make teach          # streams a layman lesson, then writes mindmap.{md,mmd,svg}
# or pick any topic id you saw under `make seed`:
uv run edu teach --topic technology.compute --user u_demo
```

Output goes to `out/<topic>/`:
- `lesson.md` — the streamed Tutor lesson with cited sources
- `mindmap.svg` — open in any browser
- `mindmap.mmd` — Mermaid source for the web client (M-8)

RAG is grounded in `seeds/notes_aws_ccp.jsonl`; the Tutor prints which sources it used before streaming.

#### Language (English / Hindi)

Persist a per-user preference, or override per call:

```bash
uv run edu set-language --user u_demo --lang hi    # save preference
uv run edu teach --topic technology.compute        # uses saved hi
uv run edu teach --topic technology.compute --lang en  # one-off override
uv run edu ask "What is a VPC?" --lang hi
```

The Tutor's lesson and the mind-map node text both follow the chosen language; universal technical terms (IAM, EC2, S3, ...) stay in English regardless.

### M-3 demo · "Examiner Socratic loop"

```bash
make examine        # streams lesson, then asks 3 questions, judges, loops on miss
# or:
uv run edu teach --topic technology.compute --interactive --user u_demo
```

After the lesson streams, you'll be prompted for an answer to each of three questions. The Examiner judges every answer and:

- **All correct (avg ≥ 0.7):** prints `Understood ✓`, emits `topic.understood` on the bus.
- **Anything wrong:** the Tutor re-teaches focused on the gap and tries again — capped at 3 iterations.
- **Still failing after 3:** prints `Needs revision`, emits `topic.misunderstood`.

Both events flow through the same Redis Streams bus the M-4+ listeners will subscribe to.

### M-4 demo · "Cards + mastery + spaced repetition"

```bash
make drill                                         # issue 6 PYQ-grounded cards for a topic
uv run edu attempt --card <card_id> --answer "..." # judges, fires card.attempted
make dashboard                                     # print mastery bars per topic
```

What happens behind the scenes when you `attempt`:

1. `AssessorAgent.grade_attempt` returns a `Judgement` (score, correct, gap).
2. The attempt is persisted in `card_attempts`.
3. `card.attempted` event lands on the Redis Streams bus.
4. **`progress_updater` listener** recomputes mastery from all attempts on the topic and writes `progress`. When mastery ≥ 0.8 it emits `topic.mastered`.
5. **`spaced_rep_scheduler` listener** stamps `due_at` on the latest attempt using SM-2-style intervals (1, 3, 7, 14, 30, 60 days; reset to 1 on miss).

### M-5 demo · "Coach + onboarding"

```bash
make onboard          # persist a profile (90 days out, 60 min/day) + emit user.onboarded
make plan-show        # 7-day plan ordered by PYQ frequency × (1 - mastery)
make replan-demo      # bump a topic to mastered=1.0 and emit plan.replan
```

The Coach scores every leaf topic by `(pyq_frequency + 0.5) × (1 - mastery)` and packs the top scorers into the next ``min(7, days_to_exam)`` days, respecting `daily_minutes` (30 min per topic). On `plan.replan`, the **`plan_replanner`** listener pulls fresh PYQ frequencies via `mcp-pyq` and writes a new plan row — mastered topics drop in priority.

### M-6 demo · "Insights + downloadable bundle"

```bash
make insight              # cutoffs / selection % / topic heatmap with provenance
make export-bundle        # builds out/artefacts/users/u_demo/topics/<topic>/bundle.zip
```

`edu insight` fans out three concurrent calls to `mcp-stats` (cutoffs, selection %, heatmap) — every number returned carries a `source`, every estimated number is flagged. `edu export` reads the topic's lesson + mind map (from `out/<topic>/`), pulls the persisted cards, calls `mcp-pdf.bundle_markdown_zip`, and writes the ZIP via the `Storage` abstraction (local filesystem in dev, R2 / S3 in prod). When `topic.mastered` fires, the **`bundle_prebuilder`** listener does the same work in the background so download is instant.

### M-7 demo · "Multi-user API"

```bash
make serve                                                  # FastAPI on :8000
curl -X POST http://localhost:8000/v1/auth/signup \
    -H 'content-type: application/json' \
    -d '{"email":"a@x.com","password":"supersecret-pw-12"}'
# → {"token": "...", "user_id": "u_..."}

TOKEN=...                                                   # paste from above
curl -X POST http://localhost:8000/v1/me/profile \
    -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' \
    -d '{"exam_id":"aws-ccp","exam_date":"2026-08-01T00:00:00Z","daily_minutes":60}'
curl http://localhost:8000/v1/me/plan -H "Authorization: Bearer $TOKEN"
```

The full v1 surface is documented at `http://localhost:8000/docs` (FastAPI auto-OpenAPI). All `/v1/me/*` endpoints require a JWT bearer token, are scoped to that user's data, and rate-limited to 60 req/min per user.

### M-8 demo · "Web walkthrough"

```bash
make web-install      # pnpm install
make serve            # backend on :8000
make web-dev          # SPA on :5173 (Vite proxies /v1 to :8000)
```

Pages: `/login`, `/onboard`, `/plan`, `/topic/:topicId`, `/progress`, `/insight`.
Auth context stores the JWT in `localStorage`; protected routes redirect to login.
The mind-map viewer dynamically imports Mermaid (10 vitest unit tests cover the
typed API client; CI runs `tsc --noEmit` + `vite build` on every PR).

### M-9 demo · "Free-tier production deploy"

Artefacts: [`apps/api/Dockerfile`](./apps/api/Dockerfile),
[`infra/docker-compose.prod.yml`](./infra/docker-compose.prod.yml),
[`infra/Caddyfile`](./infra/Caddyfile),
[`.github/workflows/deploy.yml`](./.github/workflows/deploy.yml),
[`scripts/smoke-test.sh`](./scripts/smoke-test.sh),
[`scripts/check-dashboards.sh`](./scripts/check-dashboards.sh),
[`scripts/keep-alive.sh`](./scripts/keep-alive.sh).

Tag `v*` to fire the deploy workflow against the configured VM. Smoke + cost
verification scripts run from any laptop against the deployed URL.

### M-10 demo · "Hardening"

```bash
# Local stack already up via ``make serve``
make loadtest                                     # 10 users × 5 attempts; reports p50/p95
OTEL_EXPORTER_OTLP_ENDPOINT=http://collector:4318 make serve
SENTRY_DSN=https://...@sentry.io/123 make serve
```

OTel + Sentry are opt-in (env-var driven; default off). The eval suite (Tutor
groundedness, Examiner judge precision, Assessor card quality, Coach plan
invariants) runs as a dedicated CI job so agent-quality regressions block merge.

### M-11 demo · "Volunteer acceptance"

```bash
make acceptance       # prints docs/runbook-acceptance.md
```

A fresh engineer follows [`tasks.md` Phase 10](./tasks.md) using the runbook in
[`docs/runbook-acceptance.md`](./docs/runbook-acceptance.md), reaches a green
production smoke test in ≤ 90 minutes at $0 infra spend, and signs the gate.

## Development

```bash
make lint           # ruff check + format check
make typecheck      # mypy --strict
make test           # pytest (no API calls; uses fakes)
```

## Layout

```
education/
├── apps/
│   └── api/            # FastAPI app + agents + CLI
├── mcp/                # MCP servers (added M-1+)
├── packages/
│   └── shared/         # Pydantic models, token accounting, event payloads
├── infra/
│   └── docker-compose.yml
├── .github/workflows/  # CI
└── docs/demos/         # screencasts per milestone
```

Detailed architecture in [`tech-plan.md`](./tech-plan.md). Repository is intentionally a **monorepo with `uv` workspaces** — see `tech-plan.md` §4.1.
