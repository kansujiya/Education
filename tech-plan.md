# Technical Plan — Education AI: Exam Prep Companion

> Companion to `prd.md`. Status: Draft v0.1 · Last updated: 2026-05-05

This document describes **how** the product in `prd.md` is built. It is written so a non-engineer can follow the story end-to-end, and an engineer can use it as a build blueprint. Concepts that appear repeatedly (Agent, A2A, MCP, Tool, RAG, Listener) are defined once in §2 and then used throughout.

---

## 1. The 60-second story (plain language)

Aarav opens the app. He picks "GATE" and sets his exam date. Behind the scenes:

1. The **Onboarding Agent** asks him a few questions, runs a quick diagnostic, and saves his profile.
2. The **Syllabus Agent** fetches the GATE syllabus through a small program called an **MCP server** that knows where to find it. The syllabus becomes a tree of topics in our database.
3. The **Coach Agent** reads the tree, asks a **RAG** index "which of these topics show up most in past papers?", and writes Aarav a 9-month plan.
4. Today's plan says: *learn "Operating Systems → Process Synchronisation."* The Coach **hands off** that task to the **Tutor Agent**. This handoff is what we call **A2A** (agent-to-agent).
5. The Tutor pulls a layman explanation, calls a **Tool** to draw a mind map, and chats with Aarav until he says "got it." When Aarav says "got it," a **Listener** fires an event that the Examiner is waiting for.
6. The **Examiner Agent** wakes up, asks 3 Socratic questions. Pass → it kicks an event to the **Assessor**. Fail → it kicks Aarav back to the Tutor with the gap noted.
7. The **Assessor Agent** issues flashcards drawn from real past-year questions (PYQs) using RAG. Aarav scores 8/10. An event fires.
8. The **Progress Agent** updates mastery, predicts readiness, and tells the Coach if a re-plan is needed.
9. The **Export Agent** packages the topic (notes + mind map + cards) so Aarav can download it for offline use.

Every box above is one of: **Agent** (a Claude-powered worker with a job), **Tool** (a function the agent can call), **MCP server** (a tool that lives in its own process and is reusable), **RAG** (a search-the-knowledge-base layer), **Listener** (something that watches for an event and runs code), or **A2A** (one agent handing work to another). The rest of this document is the engineering detail behind those boxes.

---

## 2. Glossary (used everywhere below)

| Term | One-line meaning | In our system |
|------|------------------|---------------|
| **Agent** | An LLM with a role, a system prompt, and a set of tools it can call in a loop. | One per role: Onboarding, Syllabus, Coach, Tutor, Examiner, Assessor, Insight, Progress, Export. |
| **Tool** | A function the LLM can decide to call (e.g. `lookup_topic`, `score_card`). | Defined in code, exposed to the agent via the Anthropic tool-use API. |
| **MCP server** | A small, separately running process that exposes a bundle of tools over the Model Context Protocol. Reusable across agents and across projects. | We run our own MCP servers for: syllabus fetch, PYQ retrieval, mind-map render, PDF export, historical-stats lookup. |
| **RAG** (Retrieval-Augmented Generation) | Search a knowledge base, paste the most relevant pieces into the prompt before the LLM answers. | Two indexes: (a) syllabus + curated notes per exam, (b) PYQ corpus. Both stored in `pgvector`. |
| **A2A** (Agent-to-Agent) | One agent invoking another agent — not just a tool, but a full sub-agent with its own loop. | Implemented as typed messages on an internal event bus + a shared session store. Coach → Tutor → Examiner → Assessor is the canonical chain. |
| **Listener** (a.k.a. event handler / hook) | Code that subscribes to an event and runs when it fires. | Used to decouple flow: e.g. `topic.understood` event → Examiner subscribes; `card.failed` → schedule spaced repetition. |
| **Session** | A persistent context for a user's interaction with one or more agents. | Stored in Postgres (durable) + Redis (hot working memory). Each agent reads/writes the slice it owns. |

---

## 3. System diagram

```
┌────────────────────────────────────────────────────────────────────────────┐
│                            CLIENTS                                         │
│     Web (React)        Mobile (React Native)        Future: CLI            │
└──────────────────────────────────┬─────────────────────────────────────────┘
                                   │  HTTPS / JSON
                                   ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                       API GATEWAY (FastAPI)                                │
│        Auth · Rate limit · Per-user routing · Versioned REST               │
└──────────────────────────────────┬─────────────────────────────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        ▼                          ▼                          ▼
┌──────────────┐         ┌──────────────────┐        ┌────────────────┐
│  ORCHESTRATOR│◀───────▶│   EVENT BUS      │◀──────▶│   LISTENERS    │
│  (Coach as   │  emits/ │  (Redis Streams) │ subs.  │ progress.upd,  │
│   conductor) │  subs.  │  topic.* events  │        │ plan.replan,   │
└──────┬───────┘         └──────────────────┘        │ nudge.idle,    │
       │ A2A handoff                                 │ revision.start │
       ▼                                             └────────────────┘
┌────────────────────────────────────────────────────────────────────────┐
│                         AGENT POOL                                     │
│  Onboarding · Syllabus · Coach · Tutor · Examiner · Assessor ·         │
│  Insight · Progress · Export                                           │
│  (each = system prompt + tool list + model: Claude Sonnet/Haiku)       │
└─────────────┬───────────────┬─────────────────┬────────────────────────┘
              │ tools         │ MCP             │ RAG
              ▼               ▼                 ▼
       ┌────────────┐  ┌──────────────┐  ┌──────────────────┐
       │ In-process │  │  MCP servers │  │  pgvector index  │
       │   tools    │  │ syllabus,    │  │  · syllabus+notes│
       │ (db, math, │  │ pyq, mindmap │  │  · PYQ corpus    │
       │  spacedrep)│  │ pdf, stats   │  │                  │
       └────────────┘  └──────────────┘  └──────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│           STATE LAYER                                                  │
│  Postgres (users, plans, progress, cards, artefacts)                   │
│  Redis    (sessions, hot agent memory, event bus)                      │
│  Object store (downloadable bundles, mind-map images)                  │
└────────────────────────────────────────────────────────────────────────┘
```

Read the diagram top-to-bottom: a client request enters the API, the API hands it to the orchestrator, the orchestrator picks the right agent, the agent uses tools / MCP / RAG, results land in the state layer, events flow on the bus, listeners react.

---

## 4. Tech stack (and why)

| Layer | Choice | Why |
|------|--------|-----|
| Backend language | **Python 3.12** | Best Claude SDK + MCP + ML ecosystem; same language for agents and RAG. |
| API framework | **FastAPI** | Async, typed, auto-OpenAPI for mobile + web clients. |
| Agent runtime | **Anthropic SDK + Claude Agent SDK** | Native tool use, streaming, MCP client built in, sessions. |
| Models | **Claude Sonnet 4.6** for Tutor / Examiner / Coach (judgement); **Claude Haiku 4.5** for high-volume cheap calls (Assessor card grading, Progress updates) | Cost / quality balance. |
| Orchestration | **Custom orchestrator + Redis Streams event bus** | Simple to read, easy to teach, swappable for LangGraph / Temporal later. |
| MCP | **Self-hosted MCP servers per integration** | Reuse across agents; clean tool boundary; standard protocol. |
| RAG | **pgvector inside Postgres** | One database to operate; sufficient at our scale; avoids a separate vector DB. |
| State | **Postgres** (durable) + **Redis** (hot + pub/sub) | Standard split. |
| Object store | **S3-compatible (MinIO in dev, S3 in prod)** | For downloadable bundles, mind-map images. |
| Auth | **Auth0 / Clerk / self-hosted with email-OTP** | Multi-user accounts; JWT to API. |
| Web client | **React + Vite** | v1 surface. |
| Mobile client | **React Native** (Expo) | Reuses TS types from the API; v1.1. |
| Observability | **OpenTelemetry traces + Langfuse for LLM traces** | Trace an entire A2A chain in one view. |

---

## 5. The Agent catalog

Each agent is one **system prompt + one tool list + one model**. They never share prompts. They communicate only via the event bus and the shared session store. This is how we get clean A2A.

| # | Agent | Job (one sentence) | Reads | Writes | Tools / MCP it uses | Talks to (A2A) | Model |
|---|-------|--------------------|-------|--------|---------------------|----------------|-------|
| 1 | **Onboarding** | Collect exam, date, level; run a quick diagnostic. | user input | `users`, `diagnostics` | `save_profile`, `score_diagnostic` (in-proc) | → Syllabus, Coach | Sonnet |
| 2 | **Syllabus** | Fetch / parse syllabus into a topic tree per exam. | exam id | `syllabus_tree` | **MCP: syllabus-server** (`fetch_syllabus`, `parse_syllabus`) | → Coach | Sonnet |
| 3 | **Coach** | Build & maintain the study plan; orchestrate daily sessions. | `users`, `syllabus_tree`, `progress` | `plans`, `sessions` | `compute_plan`, **RAG: pyq-frequency**, **MCP: stats-server** | → Tutor (handoff), ← Progress (replan signal) | Sonnet |
| 4 | **Tutor** | Teach a topic in layman language + generate mind map. | topic id, user level | `lessons`, `mindmaps` | **RAG: notes**, **MCP: mindmap-server** (`render_mindmap`) | → Examiner | Sonnet |
| 5 | **Examiner** | Run Socratic Q&A; decide "understood / not yet." | lesson context | `comprehension_log` | `ask_question`, `judge_answer` | → Assessor (pass) or → Tutor (fail) | Sonnet |
| 6 | **Assessor** | Issue PYQ-grounded cards; grade; schedule spaced rep. | topic id, comprehension | `cards`, `card_attempts` | **RAG: pyq**, `score_card`, `schedule_sr` | → Progress | Haiku |
| 7 | **Insight** | Surface historical exam data + PYQ heatmaps. | exam id, topic id | `insight_cache` | **MCP: stats-server**, **RAG: pyq** | (read-only — called by clients) | Haiku |
| 8 | **Progress** | Track mastery; predict readiness; trigger replans. | `card_attempts`, `comprehension_log` | `progress`, emits `plan.replan` | `compute_mastery`, `predict_readiness` | → Coach (via event) | Haiku |
| 9 | **Export** | Package a topic into a downloadable bundle. | topic id, user id | object store | **MCP: pdf-server**, `bundle_markdown` | (read-only — invoked on demand) | Haiku |

A few rules apply to every agent:
- **One job each.** If a prompt has two responsibilities, split it.
- **Tools over free text.** When an agent needs to do something deterministic (compute mastery, schedule SR), it calls a tool, not "reasons about it."
- **Stateless agents, stateful sessions.** The agent process holds no memory between calls; everything lives in the session store.

---

## 6. Orchestration: how agents are connected

We use **two complementary mechanisms**:

### 6.1 Direct A2A handoff (synchronous, request-time)

Used when the user is waiting and we need an immediate next step.

```
client ──▶ API ──▶ Coach.run(user_id)
                     │
                     ├─ chooses next topic
                     └─ A2A: Tutor.run(topic_id, user_id, session_id)
                                 │
                                 ├─ teaches
                                 └─ A2A: Examiner.run(session_id)
                                            │
                                            └─ returns "understood?" → client
```

A2A here is just a typed function call: `tutor.run(input: TutorInput) -> TutorOutput`, where every input/output is a Pydantic model. Each agent accepts a `session_id` so it can read/write the shared session.

### 6.2 Event bus (asynchronous, fire-and-forget)

Used when the work is decoupled or background.

```
Assessor ──emits──▶ "card.attempted" ──▶ Redis Stream
                                            │
                                            ├──▶ Progress listener (updates mastery)
                                            ├──▶ Spaced-repetition listener (re-schedules)
                                            └──▶ Analytics listener (logs metric)
```

Event payloads are versioned JSON. Listeners are independent worker processes. Adding a new listener never requires changing the emitter.

### 6.3 Event catalog (v0.1)

| Event | Emitted by | Listeners |
|-------|------------|-----------|
| `user.onboarded` | Onboarding | Coach (kick off plan), Insight (warm cache) |
| `topic.taught` | Tutor | Examiner (start Q&A) |
| `topic.understood` | Examiner | Assessor (issue cards) |
| `topic.misunderstood` | Examiner | Tutor (re-teach with gap) |
| `card.attempted` | Assessor | Progress, SpacedRep, Analytics |
| `topic.mastered` | Progress | Coach (mark plan), Export (pre-build bundle) |
| `plan.replan` | Progress / scheduler | Coach |
| `user.idle_3d` | scheduler | NudgeListener (push notification) |
| `exam.t-14d` | scheduler | Coach (switch to revision mode) |

Listeners are why the architecture stays "clear and connected": the Tutor doesn't know the Assessor exists. It emits `topic.understood` and walks away.

---

## 7. MCP servers (the reusable tool layer)

Each MCP server is one process exposing a small set of related tools. Agents connect as MCP clients. Why MCP and not just functions? Because:
- The same MCP server is reusable from any agent (and from Claude Code during dev).
- Tools have a contract; the LLM gets a typed schema.
- We can swap the implementation (e.g., switch syllabus source) without touching agents.

| MCP server | Tools exposed | Used by |
|------------|---------------|---------|
| **syllabus-server** | `fetch_syllabus(exam_id)`, `parse_syllabus(raw)`, `diff_syllabus(old, new)` | Syllabus, Coach |
| **pyq-server** | `search_pyq(topic_id, k)`, `get_pyq(id)`, `pyq_frequency(topic_id, window)` | Coach, Assessor, Insight |
| **mindmap-server** | `render_mindmap(nodes)` (returns SVG + PNG) | Tutor |
| **pdf-server** | `bundle_pdf(notes, mindmap, cards) -> url`, `bundle_markdown_zip(...)` | Export |
| **stats-server** | `cutoffs(exam_id, years)`, `selection_pct(exam_id, years)`, `topic_heatmap(exam_id)` | Insight, Coach |

All servers are stateless; persistence happens in the main DB.

---

## 8. The RAG layer

Two collections in **pgvector** (one Postgres extension; no separate DB):

### 8.1 `notes_index`
- **Source:** curated notes per topic + user-uploaded materials.
- **Embeddings:** `voyage-3` or `text-embedding-3-large` (decision in v0.1 spike).
- **Used by:** Tutor (find layman explanations + analogies), Examiner (formulate Socratic prompts).
- **Retrieval:** top-k by cosine, filtered by `topic_id` and `exam_id`.

### 8.2 `pyq_index`
- **Source:** past-year question corpus, tagged with year, exam, section, topic.
- **Embeddings:** same model.
- **Used by:** Assessor (build PYQ-grounded cards), Insight (heatmap, frequency), Coach (weight plan by PYQ density).
- **Retrieval:** hybrid search (BM25 + dense) for short PYQ stems.

Every retrieved chunk carries provenance (year, source URL or file). Provenance is rendered in the UI — never silent.

---

## 9. Listeners and background workers

A listener is a tiny process that does one thing when an event arrives. We run them as separate workers (Celery / RQ / a thin custom consumer — TBD in spike).

| Listener | Trigger | What it does |
|----------|---------|--------------|
| `progress_updater` | `card.attempted` | Recompute topic mastery. |
| `spaced_rep_scheduler` | `card.attempted` (failed) | Schedule a re-show with SM-2 / FSRS. |
| `plan_replanner` | `plan.replan` | Regenerate plan via Coach. |
| `nudge_idle` | `user.idle_3d` | Send a push notification / email. |
| `revision_switcher` | `exam.t-14d` | Flip the user into revision mode. |
| `analytics_collector` | every event | Append to analytics store. |
| `bundle_prebuilder` | `topic.mastered` | Pre-build the downloadable bundle so download is instant. |

A scheduler (cron / APScheduler) emits the time-based events (`user.idle_3d`, `exam.t-14d`).

---

## 10. Data model (essentials)

```
users(id, email, name, ...)
profiles(user_id, exam_id, exam_date, daily_minutes, level)
exams(id, name, slug)
syllabus_topics(id, exam_id, parent_id, title, weight)
plans(id, user_id, generated_at, schedule_json)
sessions(id, user_id, agent, state_json, updated_at)
lessons(id, user_id, topic_id, content_md, mindmap_url)
comprehension_log(id, session_id, question, answer, judged, score)
cards(id, user_id, topic_id, type, prompt, answer, source_pyq_id)
card_attempts(id, card_id, attempt_at, score, due_at)
progress(user_id, topic_id, mastery, last_touched, predicted_readiness)
artefacts(id, user_id, topic_id, kind, object_key)  -- downloadable bundles
events(id, name, payload_json, emitted_at)          -- audit + replay
notes_index(id, topic_id, chunk, embedding vector)  -- RAG
pyq_index(id, exam_id, topic_id, year, stem, embedding vector)
```

Multi-tenancy: every user-owned table has `user_id` and is filtered by JWT-extracted user id at the repository layer. `exams`, `syllabus_topics`, `pyq_index` are global; everything else is per-user.

---

## 11. API surface (v1, REST/JSON)

Versioned at `/v1`. All endpoints require JWT. Selected endpoints:

```
POST   /auth/signup                     -> {token}
POST   /auth/login                      -> {token}

GET    /exams                           list available exams
GET    /exams/{id}/syllabus             topic tree
GET    /exams/{id}/insights             cutoffs, selection %, heatmap

POST   /me/profile                      set exam, date, budget, run diagnostic
GET    /me/plan                         today's plan + 7-day window
POST   /me/plan/replan                  manual replan trigger

POST   /me/topics/{topic_id}/teach      starts Tutor session (SSE stream)
POST   /me/topics/{topic_id}/answer     post answer in interactive session
POST   /me/topics/{topic_id}/cards      issue today's cards
POST   /me/cards/{card_id}/attempt      submit attempt
GET    /me/progress                     dashboard data

POST   /me/topics/{topic_id}/export     trigger Export agent
GET    /me/artefacts/{id}/download      pre-signed S3 URL
```

Streaming agent responses use **Server-Sent Events** so the client can render the Tutor mid-thought.

---

## 12. End-to-end trace: "Aarav learns Process Synchronisation"

This is the same story as §1, now annotated with components.

```
Client POST /v1/me/topics/proc_sync/teach
   │
   ▼
API → Orchestrator.start_topic(user=aarav, topic=proc_sync)
   │
   ▼
Coach.run(...)                                    [Agent: Coach,  model: Sonnet]
   ├─ tool: compute_plan_for_today                [In-process tool]
   ├─ MCP: pyq-server.pyq_frequency(proc_sync)    [MCP call]
   └─ A2A: Tutor.run(topic=proc_sync, level=...)
            │
            ▼
        Tutor.run(...)                            [Agent: Tutor]
            ├─ RAG: notes_index.search(proc_sync) [RAG]
            ├─ tool: write_lesson_md
            └─ MCP: mindmap-server.render_mindmap [MCP]
            ── emits event: topic.taught ──▶ bus
   ── stream lesson + mindmap to client (SSE) ──
                                                  Examiner subscribed to topic.taught
                                                  Examiner.run(session_id)
                                                     ├─ asks 3 questions (interactive)
                                                     ├─ judge_answer × 3
                                                     └─ emits topic.understood
                                                                │
                                                                ▼
                                                          Assessor.run(...)
                                                             ├─ RAG: pyq_index.search
                                                             ├─ issues 6 cards
                                                             └─ emits card.attempted
                                                                │
                                                          ┌─────┴────┐
                                                          ▼          ▼
                                                  progress_updater  spaced_rep_scheduler
                                                          │
                                                  emits topic.mastered (if threshold)
                                                          │
                                                  ┌───────┴────────┐
                                                  ▼                ▼
                                              Coach (mark)    bundle_prebuilder
                                                                   │
                                                                   ▼
                                                          Export.run(...) → S3
```

This trace is reproducible in Langfuse: every node is one span, A2A handoffs are parent/child links, MCP and RAG calls are leaf spans.

---

## 13. Mobile + Web clients

- Both clients consume the same `/v1` API.
- Shared **TypeScript types** generated from FastAPI's OpenAPI schema (one source of truth).
- **Streaming** (Tutor / Examiner) over SSE on web, native EventSource on mobile.
- **Offline pack:** mobile downloads the artefact bundle from `/me/artefacts/{id}/download` and stores it locally. Sync queue uploads card attempts when back online.

---

## 14. Security & multi-tenancy

- JWT-based auth; tokens scoped per user.
- Repository layer always applies `WHERE user_id = current_user`; verified by integration tests.
- Per-user rate limits on agent endpoints (LLM cost protection).
- PII minimisation: only email + name; no exam-day identifiers.
- MCP servers run inside the trust boundary; tools accept only typed inputs.

---

## 15. Observability

- **Tracing:** OpenTelemetry across API → Orchestrator → Agents → Tools / MCP / RAG.
- **LLM tracing:** Langfuse — every agent run is a trace; A2A links produce a forest you can drill into.
- **Metrics:** topic-mastery rate, time-to-mastery per topic, card-pass rate, retrieval hit-rate.
- **Audit:** the `events` table is append-only and lets us replay a user's journey for support / debugging.

---

## 16. Build phases

### v0.1 — learning slice (single user, one exam, CLI/API)
Goal: prove the agent flow. Skip web, skip auth, hardcode one exam.

- FastAPI app (no auth, single fake user).
- Postgres + pgvector + Redis via docker-compose.
- All 9 agents implemented at minimum prompt quality.
- 3 MCP servers: `syllabus-server` (returns hardcoded JSON), `pyq-server` (small seeded corpus), `mindmap-server` (renders to SVG).
- RAG: pgvector with seeded notes + ~200 PYQs for one exam (e.g. AWS CCP — small corpus, easy to source).
- Event bus: Redis Streams; 3 listeners (`progress_updater`, `spaced_rep_scheduler`, `analytics_collector`).
- One end-to-end CLI demo: signup → pick exam → learn one topic → assessment → progress → export.

### v1.0 — multi-user web
- Auth (Clerk / Auth0).
- React web client.
- All MCP servers production-grade; real syllabus + PYQ ingestion pipeline.
- Insight Agent + Insight panel UI.
- Export Agent producing PDF + markdown ZIP.
- All 7 listeners running.

### v1.1 — mobile + offline + revision
- React Native client (Expo).
- Offline artefact sync.
- Revision mode (`exam.t-14d` listener) polished.
- Push notifications via `nudge_idle`.

### post-v1
- Guardian read-only view.
- Institute multi-tenancy.
- Payments.
- Switch orchestrator to LangGraph or Temporal if A2A graph grows past ~15 nodes.

---

## 17. Deployment

The whole system is just a handful of long-running processes plus stateful stores. Same shape in dev and prod; only the runner changes.

### 17.1 Process inventory

| Process | What it is | Scaling rule |
|---------|------------|--------------|
| `api`            | FastAPI app (HTTP + SSE) | horizontal, behind a load balancer |
| `orchestrator`   | Embedded in `api` for v0.1; can be split into its own service later | with `api` |
| `worker-events`  | Redis Streams consumer running listeners (`progress_updater`, `spaced_rep_scheduler`, `analytics_collector`, `bundle_prebuilder`, `nudge_idle`, `revision_switcher`) | horizontal, one consumer group, each replica grabs disjoint stream entries |
| `scheduler`      | APScheduler (cron) emitting time-based events (`user.idle_3d`, `exam.t-14d`) | exactly **one** replica (use a leader lock in Redis) |
| `mcp-syllabus`   | MCP server | horizontal, stateless |
| `mcp-pyq`        | MCP server | horizontal, stateless |
| `mcp-mindmap`    | MCP server | horizontal, stateless |
| `mcp-pdf`        | MCP server (CPU-heavy on render) | horizontal, autoscale on queue depth |
| `mcp-stats`      | MCP server | horizontal, stateless |
| `postgres`       | Postgres 16 + `pgvector` extension | managed (RDS / Neon / Supabase); read replicas later |
| `redis`          | Redis 7 (cache + pub/sub + Streams) | managed (Elasticache / Upstash) |
| `object-store`   | S3 (prod), MinIO (dev) | managed |

In v0.1 we collapse `api`, `orchestrator`, `worker-events`, and `scheduler` into one Python process to keep the dev story trivial. Splitting happens at v1.0.

### 17.2 Local development

```
docker compose up
```

`docker-compose.yml` brings up: Postgres+pgvector, Redis, MinIO, the 5 MCP servers, and the FastAPI app with hot-reload. A `make seed` target loads one demo exam, ~200 PYQs, and a fake user. New engineers should be running an end-to-end topic flow within 15 minutes of `git clone`.

Secrets in dev come from `.env` (gitignored). `ANTHROPIC_API_KEY` is the only required external secret to exercise agents.

### 17.3 Environments

| Env | Purpose | Surface | Data |
|-----|---------|---------|------|
| `dev`     | Local docker-compose. | localhost. | Seeded fake data. |
| `staging` | Pre-prod, same shape as prod. | `staging.educationai.app`. | Anonymised snapshot of prod. |
| `prod`    | Live. | `educationai.app`. | Real users. |

### 17.4 Container & runtime

- Each process ships as a container (`Dockerfile` per service, common base image).
- Multi-stage builds: tiny runtime image (`python:3.12-slim`).
- Health endpoints: `/healthz` (liveness), `/readyz` (DB + Redis + MCP reachable).
- Graceful shutdown: API drains in-flight SSE; workers ack current event before exiting.

### 17.5 Hosting (recommended path of least resistance)

| Layer | v0.1 / v1.0 | Later |
|-------|------------|-------|
| Containers   | **Fly.io** or **Railway** (single-region, simple) | **AWS ECS Fargate** or **GKE** |
| Postgres+pgvector | **Neon** or **Supabase**          | RDS Postgres + read replicas |
| Redis        | **Upstash**                                    | Elasticache cluster mode |
| Object store | **Cloudflare R2** or **AWS S3**                | same |
| CDN          | **Cloudflare** in front of the web client       | same |

Why this path: each piece is managed, free-tier-friendly for v0.1, and migrates to AWS without architectural changes.

### 17.6 Secrets & config

- All secrets in **AWS Secrets Manager** (prod) / **Doppler** or `.env` (dev).
- Config via env vars only — 12-factor.
- `ANTHROPIC_API_KEY` rotated quarterly; per-environment keys (separate dev/staging/prod billing tags).
- Service-to-service auth between API and MCP servers uses short-lived shared tokens.

### 17.7 CI/CD

- **GitHub Actions** pipeline:
  1. lint + typecheck + unit tests on PR.
  2. integration tests (spin up Postgres+Redis+MCPs in services) on PR.
  3. build & push container images on merge to `main`.
  4. deploy to `staging` automatically; deploy to `prod` on tag `v*`.
- Database migrations via **Alembic**, applied as a pre-deploy step; expand-then-contract pattern (additive migration → deploy → backfill → cleanup migration).
- Feature flags via a simple `feature_flags` table; no third-party service in v1.

### 17.8 Mobile & web release

- **Web (React + Vite):** built in CI, deployed to Cloudflare Pages / Vercel; cache-busted assets.
- **Mobile (React Native via Expo):**
  - Internal builds via **EAS Build** for every PR.
  - Beta channel via TestFlight + Play Internal.
  - Production releases via EAS Submit.
  - **Expo OTA updates** for JS-only changes; native rebuild only when modules change.
- Both clients are pinned to a backend API version; backend follows a **deprecation policy** (keep `v1` for ≥ 6 months after `v2` ships).

### 17.9 Observability in prod

- **Logs:** structured JSON → Loki / CloudWatch.
- **Metrics:** Prometheus → Grafana dashboards (RPS, p95 latency, agent run time, LLM cost per user/day).
- **Traces:** OpenTelemetry → Tempo / Honeycomb.
- **LLM traces:** Langfuse cloud (or self-hosted) — every agent run linked into one forest per user session.
- **Alerts:** error-rate spike, queue depth, LLM error/budget burn, MCP server unreachable, Postgres connection pool saturation. Pager via PagerDuty.

### 17.10 Capacity & cost guardrails

- Per-user **daily LLM budget** (tokens). Coach falls back to Haiku-only mode when budget is low.
- **Caching** of generated lessons + mind maps + cards keyed on `(topic_id, user_level)` so the same content isn't regenerated for similar users.
- **Pre-built bundles** at `topic.mastered` time (already in §9) — keeps download endpoint cheap.
- Autoscaling rules: API on RPS, workers on Redis Stream lag, `mcp-pdf` on queue depth.

### 17.11 Backup & disaster recovery

- Postgres: daily snapshots + PITR; tested restore quarterly.
- Object store: versioning on; cross-region replication in prod.
- Redis: treated as cache + transient bus — never the source of truth. Streams have a 14-day retention window so listeners can replay a missed event.
- `events` table is the durable audit log — a user's whole journey can be reconstructed from it.

### 17.12 Rollout & rollback

- Blue/green deployments behind the load balancer.
- Database migrations always backwards-compatible for one version.
- Feature-flag every new agent or listener; ship dark, enable per-cohort, then GA.
- Rollback: redeploy previous image tag; flags off; listeners with new event names can be left running because old emitters don't emit them.

---

## 18. Open spikes before v0.1 build starts

1. **Embedding model bake-off:** `voyage-3` vs `text-embedding-3-large` on PYQ retrieval recall@5.
2. **Mind-map renderer:** Mermaid (text-based, easy) vs Markmap (richer) vs custom SVG — pick on mobile-render quality.
3. **MCP transport:** stdio (simpler in dev) vs HTTP (simpler in prod) — likely stdio for v0.1, HTTP for v1.0.
4. **Coach replan cadence:** every event vs nightly batch — start nightly, escalate if needed.

---

## 19. How this maps back to the PRD

| PRD requirement | Component(s) here |
|-----------------|--------------------|
| FR-1 Account | API `/auth/*`, `users`, `profiles` |
| FR-2 Exam catalog | `exams`, `syllabus_topics`, syllabus-server, pyq-server |
| FR-3 Syllabus view | Syllabus Agent + `/exams/{id}/syllabus` |
| FR-4 Adaptive plan | Coach Agent + `plan.replan` listener |
| FR-5 Layman teaching | Tutor Agent + notes RAG |
| FR-6 Mind map | mindmap-server (MCP) |
| FR-7 Interactive session | Examiner Agent + SSE |
| FR-8 Card assessment | Assessor Agent + spaced_rep_scheduler |
| FR-9 PYQ grounding | pyq_index (RAG) + provenance in UI |
| FR-10 Historical insight | Insight Agent + stats-server |
| FR-11 Progress dashboard | Progress Agent + `/me/progress` |
| FR-12 Download | Export Agent + pdf-server + S3 |
| FR-13 Revision mode | `exam.t-14d` event + Coach |
| FR-14 Multi-user isolation | JWT + repository-layer scoping |
| FR-15 API-first | FastAPI `/v1` consumed by web + mobile |

Every PRD requirement has at least one named owner here; nothing is orphaned.
