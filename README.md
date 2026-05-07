# Education AI

An agentic AI exam-preparation companion. Multi-agent system that takes a candidate from "I have an exam on date X" to "I am ready to clear it."

> **Status:** v0.1 in progress · current milestone: **M-0 Foundations**.

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
