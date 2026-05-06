# Backlog — Education AI v0.1

> Companion to `tasks.md` (high-level phases). This file is the granular ticket-level breakdown. Anyone can pick up the next unblocked `[ ]` ticket and ship it.
>
> Status: Draft v0.1 · Last updated: 2026-05-05

## Conventions

- **ID** — `T-NNN`, sequential, never reused.
- **Size** — `XS` (<30 min) · `S` (30 min–2 h) · `M` (2–4 h) · `L` (4–8 h). Anything larger gets split.
- **Deps** — list of ticket IDs that must be done first. Empty = pickable now.
- **DoD** — Definition of Done; the acceptance check.
- **Owner** — fill in when picked up.

Format:

```
[ ] T-NNN  Title
       Size · Deps · Owner
       DoD: ...
```

Tickets are grouped by **epic**. Epics are mostly sequential, but unblocked tickets across epics can run in parallel.

---

## EP-0 — Repo, tooling, and CI scaffolding

```
[ ] T-001  Initialise uv workspace at repo root
       XS · deps: — · owner: —
       DoD: `uv sync` succeeds; root pyproject.toml declares workspaces apps/*, mcp/*, packages/*.

[ ] T-002  Create monorepo directory layout (tasks.md §1.1)
       XS · deps: T-001 · owner: —
       DoD: `tree -L 2` matches the layout in tasks.md.

[ ] T-003  Add ruff + mypy + pre-commit
       S · deps: T-001 · owner: —
       DoD: `pre-commit run -a` passes on a hello-world file.

[ ] T-004  Add Makefile (`make dev`, `make seed`, `make test`, `make lint`, `make migrate`)
       S · deps: T-002 · owner: —
       DoD: `make help` lists all targets; `make lint` passes.

[ ] T-005  Add .env.example with every variable referenced anywhere
       XS · deps: — · owner: —
       DoD: All vars from tasks.md Phase 10 §7 are listed with comments.

[ ] T-006  Write README quickstart (≤ 30 lines: clone → make dev → curl healthz)
       S · deps: T-004 · owner: —
       DoD: A fresh engineer following the README hits a green healthz in <15 min.

[ ] T-007  GitHub Actions CI workflow (lint + typecheck + tests, matrix per service)
       M · deps: T-003, T-004 · owner: —
       DoD: PR to main runs the workflow green; uses path filters so only changed services rebuild.

[ ] T-008  GitHub Actions deploy workflow (tag-based SSH deploy)
       S · deps: T-007 · owner: —
       DoD: Pushing tag `v0.0.0-test` triggers a noop deploy successfully against a test VM.
```

## EP-1 — Shared package (`packages/shared`)

```
[ ] T-010  Set up packages/shared as a uv-installable package
       XS · deps: T-001 · owner: —
       DoD: `from shared.models import User` works in apps/api.

[ ] T-011  Pydantic v2: User, Profile models
       S · deps: T-010 · owner: —
       DoD: roundtrip JSON test passes.

[ ] T-012  Pydantic v2: Exam, SyllabusTopic, Plan models
       S · deps: T-010 · owner: —
       DoD: roundtrip JSON test passes; supports nested topic tree.

[ ] T-013  Pydantic v2: Lesson, Mindmap, ComprehensionLog models
       S · deps: T-010 · owner: —
       DoD: roundtrip JSON test passes.

[ ] T-014  Pydantic v2: Card, CardAttempt, SR-state models
       S · deps: T-010 · owner: —
       DoD: roundtrip JSON test passes.

[ ] T-015  Pydantic v2: Progress, Mastery, ReadinessPrediction models
       S · deps: T-010 · owner: —
       DoD: roundtrip JSON test passes.

[ ] T-016  Event payload models (one per event in tech-plan §6.3)
       M · deps: T-010 · owner: —
       DoD: Every event has a typed payload; envelope includes `name`, `version`, `emitted_at`, `correlation_id`.

[ ] T-017  Tool I/O schemas (every tool in tech-plan §5.3)
       M · deps: T-010 · owner: —
       DoD: Every tool has a TypedInput/TypedOutput pair; smoke test asserts schemas serialise.
```

## EP-2 — Database + migrations

```
[ ] T-020  docker-compose: Postgres (pgvector image) service
       XS · deps: T-002 · owner: —
       DoD: `docker compose up -d postgres` healthy.

[ ] T-021  Alembic init + base config
       S · deps: T-020 · owner: —
       DoD: `alembic current` returns empty.

[ ] T-022  Initial migration: every table in tech-plan §10
       L · deps: T-021 · owner: —
       DoD: `alembic upgrade head` applies cleanly; downgrade reverses.

[ ] T-023  Enable pgvector extension as part of migration
       XS · deps: T-022 · owner: —
       DoD: `SELECT extname FROM pg_extension WHERE extname='vector';` returns a row.

[ ] T-024  ANN index on notes_index.embedding (ivfflat)
       S · deps: T-022 · owner: —
       DoD: `EXPLAIN` on a vector query uses the index.

[ ] T-025  ANN index on pyq_index.embedding + tsvector index for hybrid search
       S · deps: T-022 · owner: —
       DoD: Hybrid query plan uses both indexes.

[ ] T-026  Repository layer with user_id scoping enforced at query time
       M · deps: T-022, T-011 · owner: —
       DoD: Integration test: a query for user A never returns user B's rows.

[ ] T-027  Seed loader: seeds/exam_aws_ccp.json + seeds/pyqs.jsonl
       S · deps: T-026 · owner: —
       DoD: `make seed` populates the DB; counts match seed file lengths.
```

## EP-3 — Local infra services

```
[ ] T-030  docker-compose: Redis 7-alpine
       XS · deps: T-002 · owner: —
       DoD: `redis-cli ping` returns PONG.

[ ] T-031  docker-compose: MinIO + create bucket on startup
       S · deps: T-002 · owner: —
       DoD: A test put/get round-trips through MinIO.

[ ] T-032  docker-compose: Langfuse self-hosted (web + db)
       S · deps: T-002 · owner: —
       DoD: Langfuse UI loads at http://localhost:3000.

[ ] T-033  Caddy reverse proxy service in compose
       S · deps: T-002 · owner: —
       DoD: https://localhost reaches the API via Caddy with a self-signed cert.
```

## EP-4 — Agent runtime (the BaseAgent)

```
[ ] T-040  BaseAgent class skeleton (name, system_prompt, tools, model, run)
       M · deps: T-010 · owner: —
       DoD: A trivial echo agent passes a unit test.

[ ] T-041  Anthropic SDK wrapper with prompt caching (cache_control on system prompt + RAG context)
       M · deps: T-040 · owner: —
       DoD: A second identical call shows ≥80% input-token cache hit in Langfuse.

[ ] T-042  Tool registration + JSON-schema export for Anthropic tool-use
       S · deps: T-040, T-017 · owner: —
       DoD: A tool defined in Python is callable by the LLM in a unit test.

[ ] T-043  Streaming responses (SSE-friendly chunks)
       S · deps: T-041 · owner: —
       DoD: Streaming test yields chunks before completion.

[ ] T-044  Token-cost accounting + Langfuse spans per agent run
       M · deps: T-041 · owner: —
       DoD: Each agent run produces a Langfuse trace with cost_usd populated.

[ ] T-045  Session read/write tools (Redis-backed)
       S · deps: T-040, T-030 · owner: —
       DoD: Two consecutive runs with the same session_id share state.

[ ] T-046  emit_event tool (Redis Streams writer)
       S · deps: T-040, T-030, T-016 · owner: —
       DoD: Emitted event appears in `XREAD` on the right stream.

[ ] T-047  Per-user daily token budget guard
       S · deps: T-044 · owner: —
       DoD: When budget exceeded, agent falls back to Haiku and logs a warning.

[ ] T-048  vcrpy fixtures harness for deterministic agent unit tests
       M · deps: T-040 · owner: —
       DoD: Agent tests run offline using cassette playback.
```

## EP-5 — MCP servers (one ticket per server)

```
[ ] T-050  mcp-syllabus: Dockerfile + tools (fetch_syllabus, parse_syllabus, diff_syllabus)
       M · deps: T-002 · owner: —
       DoD: Agent can call fetch_syllabus over stdio and get the seeded JSON back.

[ ] T-051  mcp-pyq: Dockerfile + bundled sentence-transformers/all-MiniLM-L6-v2
       L · deps: T-002, T-025 · owner: —
       DoD: search_pyq returns top-k results with provenance; embeddings computed locally.

[ ] T-052  mcp-mindmap: Dockerfile + Mermaid CLI; tool render_mindmap → SVG
       M · deps: T-002 · owner: —
       DoD: Given a node tree, returns valid SVG that renders in a browser.

[ ] T-053  mcp-pdf: Dockerfile + WeasyPrint; tools bundle_pdf, bundle_markdown_zip
       M · deps: T-002, T-031 · owner: —
       DoD: Given lesson + mindmap + cards, writes a PDF + zip to MinIO and returns URL.

[ ] T-054  mcp-stats: Dockerfile + tools cutoffs, selection_pct, topic_heatmap
       S · deps: T-002 · owner: —
       DoD: Returns the seeded historical data with citations.

[ ] T-055  Smoke-test harness: spin all MCP servers, call each tool once
       S · deps: T-050..T-054 · owner: —
       DoD: `make test-mcp` is green.
```

## EP-6 — RAG layer

```
[ ] T-060  Embedding pipeline: chunk + embed + upsert into notes_index
       M · deps: T-024, T-051 · owner: —
       DoD: Backfill seeded notes; row count matches expected.

[ ] T-061  Embedding pipeline for pyq_index from seeds/pyqs.jsonl
       S · deps: T-025, T-051 · owner: —
       DoD: ~200 PYQs embedded with year/section tags.

[ ] T-062  Hybrid retrieval: dense + tsvector + reciprocal-rank fusion
       M · deps: T-024, T-025 · owner: —
       DoD: Recall@5 ≥ 0.7 on a hand-labelled eval set of 30 queries.

[ ] T-063  Provenance always returned with every retrieved chunk
       S · deps: T-062 · owner: —
       DoD: Every API response that surfaces a fact includes its source.
```

## EP-7 — Agents (one ticket per agent in tech-plan §5.1)

```
[ ] T-070  Onboarding Agent (prompt chaining)
       M · deps: T-040..T-048, T-027 · owner: —
       DoD: Given user input, writes profile + diagnostic; emits user.onboarded.

[ ] T-071  Syllabus Agent (wraps mcp-syllabus)
       S · deps: T-040..T-048, T-050 · owner: —
       DoD: Given exam_id, populates syllabus_topics; idempotent.

[ ] T-072  Coach Agent — orchestrator-workers + routing
       L · deps: T-070, T-071, T-051, T-054, T-062 · owner: —
       DoD: Given user_id, produces a 7-day plan weighted by PYQ frequency.

[ ] T-073  Tutor Agent — prompt chaining + parallelisation
       L · deps: T-040..T-048, T-052, T-062 · owner: —
       DoD: Given topic_id + user_level, produces lesson md + mindmap SVG; parallel RAG + render proven by trace.

[ ] T-074  Examiner Agent — routing + evaluator-optimiser loop with Tutor
       L · deps: T-073 · owner: —
       DoD: Asks ≥3 comprehension questions; emits topic.understood or topic.misunderstood; loop hard-capped at 3.

[ ] T-075  Assessor Agent (wraps mcp-pyq, writes cards)
       M · deps: T-040..T-048, T-051, T-061 · owner: —
       DoD: Given topic_id, issues 6 PYQ-grounded cards (mix of recall/MCQ/short-answer); SR scheduling correct.

[ ] T-076  Insight Agent (parallelisation)
       M · deps: T-040..T-048, T-054, T-062 · owner: —
       DoD: Given exam_id + topic_id, returns cutoffs + selection % + heatmap with citations; fan-out visible in trace.

[ ] T-077  Progress Agent (pure-function tools + emits)
       M · deps: T-040..T-048, T-014 · owner: —
       DoD: On card.attempted, recomputes mastery; emits topic.mastered when threshold crossed; predicts readiness.

[ ] T-078  Export Agent (wraps mcp-pdf)
       S · deps: T-040..T-048, T-053 · owner: —
       DoD: Given topic_id + user_id, writes a bundle to MinIO and returns a pre-signed URL.

[ ] T-079  Coach: nightly autonomous replan loop (with cost cap)
       M · deps: T-072, T-077 · owner: —
       DoD: Given progress signal, regenerates plan; max 20 tool calls; cost tracked.
```

## EP-8 — Event bus + listeners

```
[ ] T-080  Redis Streams setup with consumer groups (per worker class)
       S · deps: T-030 · owner: —
       DoD: Two replicas of the same group split events; ack works.

[ ] T-081  Listener: progress_updater on card.attempted
       S · deps: T-080, T-077 · owner: —
       DoD: Mastery updates within 1s of event.

[ ] T-082  Listener: spaced_rep_scheduler on card.attempted (failed)
       S · deps: T-080, T-075 · owner: —
       DoD: due_at set per SM-2 / FSRS rules.

[ ] T-083  Listener: plan_replanner on plan.replan
       S · deps: T-080, T-072 · owner: —
       DoD: Re-runs Coach; new plan persisted.

[ ] T-084  Listener: nudge_idle (driven by scheduler)
       S · deps: T-080 · owner: —
       DoD: Logs a nudge intent; later wires to push notifications.

[ ] T-085  Listener: revision_switcher (driven by scheduler at T-14d)
       S · deps: T-080, T-072 · owner: —
       DoD: User flagged into revision mode; Coach plans accordingly.

[ ] T-086  Listener: analytics_collector (every event)
       S · deps: T-080 · owner: —
       DoD: events table append-only; replayable.

[ ] T-087  Listener: bundle_prebuilder on topic.mastered
       S · deps: T-080, T-078 · owner: —
       DoD: Artefact pre-built so download endpoint is a static GET.

[ ] T-088  Scheduler service: APScheduler emitting time-based events with leader lock in Redis
       M · deps: T-080 · owner: —
       DoD: Two replicas → only one emits; failover within 30s of leader death.
```

## EP-9 — API surface

```
[ ] T-090  FastAPI app skeleton + healthz/readyz
       S · deps: T-020, T-030 · owner: —
       DoD: Both endpoints return 200 with dependency status.

[ ] T-091  Auth middleware (Supabase JWT verification)
       M · deps: T-090 · owner: —
       DoD: Protected route returns 401 without token, 200 with valid token.

[ ] T-092  Per-user rate limit middleware
       S · deps: T-091 · owner: —
       DoD: Burst above limit returns 429.

[ ] T-093  Endpoints: /v1/auth/* (signup/login pass-through to Supabase)
       S · deps: T-091 · owner: —
       DoD: e2e test signs up + logs in.

[ ] T-094  Endpoints: /v1/exams (list + syllabus + insights)
       M · deps: T-071, T-076 · owner: —
       DoD: e2e returns syllabus tree and insight panel.

[ ] T-095  Endpoints: /v1/me/profile (POST), /v1/me/plan (GET, POST replan)
       M · deps: T-070, T-072 · owner: —
       DoD: e2e onboarding + plan retrieval works.

[ ] T-096  Endpoint: /v1/me/topics/{id}/teach (SSE)
       L · deps: T-073, T-043 · owner: —
       DoD: Browser EventSource receives lesson chunks live.

[ ] T-097  Endpoint: /v1/me/topics/{id}/answer (SSE)
       M · deps: T-074, T-043 · owner: —
       DoD: Comprehension Q&A streams over SSE.

[ ] T-098  Endpoints: /v1/me/topics/{id}/cards, /v1/me/cards/{id}/attempt
       M · deps: T-075 · owner: —
       DoD: Card issue + attempt round-trips; events emitted.

[ ] T-099  Endpoints: /v1/me/progress, /v1/me/topics/{id}/export, /v1/me/artefacts/{id}/download
       M · deps: T-077, T-078 · owner: —
       DoD: Dashboard data returned; pre-signed S3 URL works.

[ ] T-100  OpenAPI export + openapi-typescript generation in CI
       S · deps: T-090 · owner: —
       DoD: Web client imports generated types; build succeeds.
```

## EP-10 — Web client (v1.0)

```
[ ] T-110  Vite + React + TS scaffold under apps/web with TanStack Query + auth SDK
       M · deps: T-100 · owner: —
       DoD: Dev server runs; healthz visible from browser.

[ ] T-111  Auth screens (signup/login/forgot)
       M · deps: T-110, T-091 · owner: —
       DoD: User can sign up + log in.

[ ] T-112  Onboarding wizard (exam, date, daily minutes, diagnostic)
       L · deps: T-110, T-095 · owner: —
       DoD: Wizard writes profile + kicks off plan generation.

[ ] T-113  Topic learning view with SSE (lesson + Mermaid render)
       L · deps: T-096, T-097 · owner: —
       DoD: Lesson streams live; Mermaid mind map renders inline.

[ ] T-114  Card review UI (flip + MCQ + short-answer)
       M · deps: T-098 · owner: —
       DoD: Round-trips through API; correct/incorrect feedback visible.

[ ] T-115  Progress dashboard
       M · deps: T-099 · owner: —
       DoD: Mastery %, days to exam, weak topics, predicted readiness all rendered.

[ ] T-116  Insight panel (cutoffs, selection %, heatmap with citations)
       M · deps: T-094 · owner: —
       DoD: Numbers render with sources; "AI-estimated" flag where applicable.

[ ] T-117  Per-topic download button → pre-signed URL flow
       S · deps: T-099 · owner: —
       DoD: Click downloads the bundle; artefact opens correctly.

[ ] T-118  Cloudflare Pages deployment wired to main
       S · deps: T-007 · owner: —
       DoD: pages.dev URL updates on push to main.
```

## EP-11 — Deployment to free infra (matches tasks.md Phase 10)

```
[ ] T-120  Provision Oracle Always-Free ARM VM (or Hetzner CX22 fallback)
       S · deps: — · owner: —
       DoD: SSH succeeds; 4 GB swap on; ufw rules active.

[ ] T-121  Install Docker + clone repo + set up .env on VM
       S · deps: T-120 · owner: —
       DoD: `docker compose ps` lists all services.

[ ] T-122  Set up Neon Postgres + run migrations remotely
       S · deps: T-022 · owner: —
       DoD: `alembic current` on Neon shows head; pgvector enabled.

[ ] T-123  Set up Cloudflare R2 bucket + access tokens; route artefacts there
       S · deps: T-031 · owner: —
       DoD: Bundle write/read round-trips against R2 in prod.

[ ] T-124  Caddy + nip.io for free TLS
       S · deps: T-033, T-121 · owner: —
       DoD: https://<vm-ip>.nip.io/healthz returns 200 with valid cert.

[ ] T-125  Deploy web client to Cloudflare Pages
       S · deps: T-118 · owner: —
       DoD: Public URL serves the app and reaches the API.

[ ] T-126  Wire GitHub Actions deploy workflow secrets (VM_HOST, VM_SSH_KEY)
       XS · deps: T-008, T-120 · owner: —
       DoD: Pushing tag `v0.1.0-rc1` deploys successfully.

[ ] T-127  Add keep-alive cron to prevent Oracle reclaim
       XS · deps: T-120 · owner: —
       DoD: `crontab -l` shows the 5-min healthz curl.

[ ] T-128  Self-host Langfuse on the VM and route LF_* env to it
       S · deps: T-032, T-121 · owner: —
       DoD: A real prod request shows up as a Langfuse trace.

[ ] T-129  Production smoke test (tasks.md Phase 10 §14)
       S · deps: T-120..T-128 · owner: —
       DoD: signup + profile + teach SSE all green from outside the VM.

[ ] T-130  Day-1 cost verification across all dashboards
       XS · deps: T-129 · owner: —
       DoD: Oracle / Neon / R2 / Pages dashboards all show $0; Anthropic spend alert set at $5.
```

## EP-12 — Observability + ops

```
[ ] T-140  OpenTelemetry instrumentation across api, worker, scheduler, MCP servers
       M · deps: T-090 · owner: —
       DoD: A single user request produces one connected trace forest.

[ ] T-141  Grafana Cloud free tier wired for metrics + logs
       S · deps: T-140 · owner: —
       DoD: Basic dashboard shows RPS, p95 latency, agent run time.

[ ] T-142  Sentry free tier wired (api + worker + web)
       S · deps: T-090, T-110 · owner: —
       DoD: A test exception shows up in Sentry with source map.

[ ] T-143  Alert: Anthropic spend > $5/day
       XS · deps: T-141 · owner: —
       DoD: Triggering condition fires a notification (email).

[ ] T-144  Runbook: cost-spike response (tasks.md "When Anthropic spend spikes")
       XS · deps: — · owner: —
       DoD: One-page runbook in repo.

[ ] T-145  Backup: nightly Neon → R2 dump
       S · deps: T-122, T-123 · owner: —
       DoD: A full restore from yesterday's dump succeeds in staging.
```

## EP-13 — Quality gates before calling v0.1 "done"

```
[ ] T-150  E2E test suite: full user journey signup→export, run in CI
       L · deps: T-099, T-110..T-117 · owner: —
       DoD: Green in CI against ephemeral compose stack.

[ ] T-151  Agent regression evals (Examiner judge precision, Assessor card quality, Tutor groundedness)
       L · deps: T-074, T-075, T-073 · owner: —
       DoD: Eval scores meet thresholds set in pyproject.toml; fails CI if regressed.

[ ] T-152  Load test: 10 concurrent users completing one topic loop
       M · deps: T-129 · owner: —
       DoD: p95 latency < 5s on Tutor stream; no errors.

[ ] T-153  Security pass: JWT scoping, repository scoping, MCP input validation
       M · deps: T-091, T-026 · owner: —
       DoD: Negative-path tests prove user A can't read user B's data via any endpoint.

[ ] T-154  Accessibility quick pass on web client (keyboard, contrast, alt text)
       S · deps: T-110..T-117 · owner: —
       DoD: Lighthouse a11y ≥ 90.

[ ] T-155  v0.1 acceptance gate (tasks.md Phase 11)
       XS · deps: T-150..T-154, T-129 · owner: —
       DoD: A fresh engineer follows tasks.md Phase 10 to a green smoke test in ≤90 min at $0 infra.
```

---

## Summary by epic

| Epic | Tickets | Total size |
|------|---------|------------|
| EP-0  Repo & CI                  | 8  | ~1 day |
| EP-1  Shared models              | 8  | ~1 day |
| EP-2  Database                   | 8  | ~1.5 days |
| EP-3  Local infra                | 4  | ~0.5 day |
| EP-4  Agent runtime              | 9  | ~3 days |
| EP-5  MCP servers                | 6  | ~2.5 days |
| EP-6  RAG                        | 4  | ~1.5 days |
| EP-7  Agents                     | 10 | ~5 days |
| EP-8  Event bus + listeners      | 9  | ~2 days |
| EP-9  API surface                | 11 | ~3 days |
| EP-10 Web client                 | 9  | ~4 days |
| EP-11 Deployment                 | 11 | ~1 day |
| EP-12 Observability              | 6  | ~1.5 days |
| EP-13 Quality gates              | 6  | ~3 days |
| **Total**                        | **109** | **~30 working days (~6 weeks solo)** |

## Critical path (sequence that gates the demo)

```
T-001 → T-010 → T-022 → T-040 → T-050 → T-060 → T-070 → T-072 → T-073 → T-074 → T-075 → T-077 → T-090 → T-096 → T-129
```

Anything not on this path can run in parallel.

## How to start tomorrow

Pick `T-001`. Ship it. Move down the list. Update `Owner` when you start, tick the box when DoD passes.
