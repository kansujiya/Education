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
