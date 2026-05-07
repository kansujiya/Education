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
