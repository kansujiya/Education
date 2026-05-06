# Tasks — Education AI v0.1

> Companion to `prd.md` and `tech-plan.md`. Status: Draft v0.1 · Last updated: 2026-05-05

This document is a **build runbook**. Anyone with this file, the PRD, and the tech plan should be able to take the project from empty repo to deployed v0.1 on free infrastructure. Tasks are ordered. Every task has a clear "done when" check.

---

## How to use this document

- Tasks are grouped into **phases**; finish a phase before starting the next.
- Each task starts with `[ ]` — tick it when complete.
- Commands assume **Linux/macOS**. Windows users: use WSL2.
- "Done when" is the acceptance check; do not move on until it passes.
- Phase 10 is the **step-by-step deployment guide** — the part that doesn't fit in `tech-plan.md`.

---

## Phase 0 — Accounts and local tools

### 0.1 Free accounts to create (no credit card unless noted)

- [ ] **GitHub** — https://github.com/signup
- [ ] **Anthropic Console** — https://console.anthropic.com/ (claim $5 signup credit)
- [ ] **Oracle Cloud** — https://signup.cloud.oracle.com/ (credit card required for verification; you stay on Always-Free)
- [ ] **Neon** — https://console.neon.tech/signup (Postgres + `pgvector`)
- [ ] **Cloudflare** — https://dash.cloudflare.com/sign-up (Pages + R2)
- [ ] **Supabase** — https://supabase.com/dashboard/sign-up (Auth, optional alternative DB)
- [ ] **Langfuse Cloud** — https://cloud.langfuse.com (or skip; we self-host)

### 0.2 Local tools

- [ ] `git` ≥ 2.40 — `git --version`
- [ ] `docker` + `docker compose` v2 — `docker --version && docker compose version`
- [ ] `uv` (Python package manager) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- [ ] `node` ≥ 20 + `pnpm` — for the web client
- [ ] An SSH key — `ssh-keygen -t ed25519 -C "you@example.com"` (you will paste the public key into Oracle)

**Done when:** every command above prints a version.

---

## Phase 1 — Repository scaffold

### 1.1 Directory layout

Create this structure in the repo:

```
education/
├── apps/
│   ├── api/                 # FastAPI app (orchestrator + agents inline for v0.1)
│   ├── worker/              # event-bus consumer (listeners)
│   ├── scheduler/           # APScheduler emitter
│   └── web/                 # React + Vite client (v1.0)
├── mcp/
│   ├── syllabus/            # MCP server: fetch + parse syllabus
│   ├── pyq/                 # MCP server: PYQ retrieval + local embeddings
│   ├── mindmap/             # MCP server: Mermaid → SVG
│   ├── pdf/                 # MCP server: WeasyPrint
│   └── stats/               # MCP server: cutoffs, selection %, heatmap
├── packages/
│   └── shared/              # Pydantic models, event payloads, tool schemas
├── infra/
│   ├── docker-compose.yml
│   ├── Caddyfile            # TLS reverse proxy in prod
│   └── alembic/             # DB migrations
├── seeds/
│   ├── exam_aws_ccp.json    # one demo exam
│   └── pyqs.jsonl           # ~200 seeded PYQs
├── .github/workflows/       # CI
├── .env.example
├── pyproject.toml
└── README.md
```

- [ ] Tasks: create the directories above.
- [ ] Add `.env.example` with every variable name (no secrets).
- [ ] Add `pyproject.toml` listing deps from tech-plan §5.4.

**Done when:** `tree -L 2` shows the layout above and `uv sync` resolves dependencies.

### 1.2 Shared package (Pydantic models)

- [ ] Define `User`, `Profile`, `Topic`, `Lesson`, `Card`, `CardAttempt`, `Plan` models.
- [ ] Define event payload models for every event in tech-plan §6.3 (`user.onboarded`, `topic.taught`, `topic.understood`, `card.attempted`, `topic.mastered`, `plan.replan`, `user.idle_3d`, `exam.t-14d`).
- [ ] Define tool input/output models for every tool in tech-plan §5.3.

**Done when:** `mypy packages/shared` is clean and `pytest packages/shared` passes a model-roundtrip test.

---

## Phase 2 — Local dev environment

### 2.1 docker-compose for local

`infra/docker-compose.yml` brings up: Postgres + pgvector, Redis, MinIO (S3-compatible), Langfuse, the 5 MCP servers, and the API.

- [ ] Postgres image: `pgvector/pgvector:pg16`
- [ ] Redis image: `redis:7-alpine`
- [ ] MinIO image: `minio/minio:latest`
- [ ] One service per MCP server, built from `mcp/<name>/Dockerfile`
- [ ] API service, built from `apps/api/Dockerfile`

- [ ] `make seed` target: load `seeds/exam_aws_ccp.json` + `seeds/pyqs.jsonl`.
- [ ] `make dev` target: `docker compose up --build`.

**Done when:** `make dev` brings everything up; `curl http://localhost:8000/healthz` returns 200.

### 2.2 Database migrations

- [ ] Alembic init under `infra/alembic`.
- [ ] First migration: every table in tech-plan §10.
- [ ] Enable `pgvector` extension as part of the migration.

**Done when:** `alembic upgrade head` succeeds against the Compose Postgres.

---

## Phase 3 — Build the agentic core

### 3.1 Agent skeleton (do once, copy 9 times)

- [ ] Define a `BaseAgent` class with: `name`, `system_prompt`, `tools`, `model`, `run(input) -> output`.
- [ ] Wrap the Anthropic SDK with: prompt caching (`cache_control`), tool calling, streaming, token accounting → emit to Langfuse.
- [ ] Add `read_session` / `write_session` tool to every agent (Redis-backed).
- [ ] Add `emit_event` tool to every agent (Redis Streams).

**Done when:** a "hello world" agent can run, call a tool, and a Langfuse trace is visible.

### 3.2 Implement the 9 agents (tech-plan §5.1)

For each agent below, the deliverable is: system prompt + tool list + Pydantic input/output + a unit test.

- [ ] **Onboarding** — pattern: prompt chaining
- [ ] **Syllabus** — wraps `mcp-syllabus` tools
- [ ] **Coach** — pattern: orchestrator-workers + routing + autonomous (nightly replan)
- [ ] **Tutor** — pattern: prompt chaining + parallelisation (RAG + mind-map)
- [ ] **Examiner** — pattern: routing + evaluator-optimiser (with Tutor)
- [ ] **Assessor** — wraps `mcp-pyq` and writes cards
- [ ] **Insight** — pattern: parallelisation
- [ ] **Progress** — pure-function tools + emits `topic.mastered` / `plan.replan`
- [ ] **Export** — wraps `mcp-pdf`

**Done when:** each agent has a green unit test using `vcrpy` fixtures (deterministic LLM responses).

### 3.3 MCP servers

For each, deliverable is: tool definitions + a Dockerfile + a smoke test.

- [ ] `mcp-syllabus` — `fetch_syllabus`, `parse_syllabus`, `diff_syllabus` (v0.1 returns the seeded JSON)
- [ ] `mcp-pyq` — `search_pyq`, `get_pyq`, `pyq_frequency`; embeds locally via `sentence-transformers`
- [ ] `mcp-mindmap` — `render_mindmap` (Mermaid CLI in container)
- [ ] `mcp-pdf` — `bundle_pdf`, `bundle_markdown_zip` (WeasyPrint)
- [ ] `mcp-stats` — `cutoffs`, `selection_pct`, `topic_heatmap` (returns seeded data in v0.1)

**Done when:** an agent can call any MCP tool over stdio and the call traces in Langfuse.

### 3.4 RAG indexes

- [ ] Backfill `notes_index` from seeded notes per topic.
- [ ] Backfill `pyq_index` from `seeds/pyqs.jsonl`.
- [ ] Hybrid search function: dense (`pgvector`) + BM25 (`tsvector`) with reciprocal-rank fusion.
- [ ] Provenance always returned with every chunk.

**Done when:** a query for "process synchronisation" returns ≥3 PYQs tagged with year/section.

### 3.5 Event bus and listeners

- [ ] Redis Streams setup with consumer groups.
- [ ] Listener `progress_updater` — recompute mastery on `card.attempted`.
- [ ] Listener `spaced_rep_scheduler` — schedule SR on failed card.
- [ ] Listener `analytics_collector` — append every event to analytics table.
- [ ] Listener `bundle_prebuilder` — pre-build artefact on `topic.mastered`.
- [ ] Listener `nudge_idle` and `revision_switcher` (driven by scheduler).
- [ ] Listener `plan_replanner` — reruns Coach when `plan.replan` fires.

**Done when:** a `card.attempted` event triggers all three subscribers and shows in the trace forest.

### 3.6 API surface

- [ ] Every endpoint in tech-plan §11.
- [ ] JWT auth middleware (Supabase or Clerk; pluggable).
- [ ] SSE streaming for `/me/topics/{topic_id}/teach` and `/me/topics/{topic_id}/answer`.
- [ ] Rate limit per user.
- [ ] Generated OpenAPI consumed by `openapi-typescript` for the web client.

**Done when:** end-to-end smoke test passes: signup → set profile → teach → answer → cards → progress → export.

---

## Phase 4 — Web client (v1.0 surface)

- [ ] Vite + React + TS + TanStack Query.
- [ ] Auth screens (Supabase / Clerk SDK).
- [ ] Onboarding wizard.
- [ ] Topic learning view with SSE streaming.
- [ ] Mind-map renderer (Mermaid).
- [ ] Card review UI.
- [ ] Progress dashboard.
- [ ] Insight panel (cutoffs, heatmap).
- [ ] Download button per topic.

**Done when:** the same end-to-end flow works through the browser.

---

## Phase 5 — Mobile client (v1.1, deferred)

- [ ] Expo project, shared TS types from OpenAPI.
- [ ] EAS Build configured.
- [ ] Offline artefact sync.
- [ ] Push notifications.

---

# Phase 10 — Deployment runbook (step-by-step)

This is the part that anyone should be able to follow without prior infra experience. Everything below is on the **free path** from tech-plan §18. End state: a public HTTPS URL serving the API + a Cloudflare Pages URL serving the web client, total infra cost **$0/month** plus Anthropic per-token usage.

> Time required: ~90 minutes the first time.

## Step 1 — Pick your machine and prepare locally

On your laptop:

```bash
# Generate an SSH key if you don't have one
ssh-keygen -t ed25519 -C "you@example.com" -f ~/.ssh/education_ed25519

# Copy the public key — you'll paste it into Oracle in Step 2
cat ~/.ssh/education_ed25519.pub
```

## Step 2 — Provision the Oracle Always-Free ARM VM

1. Sign in to https://cloud.oracle.com.
2. Top-left menu → **Compute → Instances → Create instance**.
3. **Name:** `education-vm`.
4. **Image:** click *Change image* → **Canonical Ubuntu 22.04**.
5. **Shape:** click *Change shape* → choose **Ampere**, select **VM.Standard.A1.Flex**, set **OCPUs = 4**, **Memory = 24 GB**. (This is within the Always-Free allowance.)
6. **Networking:** keep the default VCN; ensure *Assign a public IPv4 address* is checked.
7. **SSH keys:** paste the public key from Step 1.
8. Click **Create**. Wait ~2 minutes until status = *Running*. Note the **Public IPv4 address**.

If you get *Out of capacity* (common on free ARM): retry in a different *Availability Domain* under the same region. If still failing: fall back to a **Google Cloud `e2-micro`** or to **Step 2b** below.

> **Step 2b (fallback):** Hetzner CX22 — €4.51/month (~$5). Sign up at https://hetzner.com/cloud, create a CX22 in Falkenstein, paste the SSH key, copy the IP. Skip the Oracle-specific firewall steps and use `ufw` directly.

### 2.1 Open ports in Oracle's network rules

1. Compute → Instances → click your VM → **Virtual cloud network** link → **Security Lists** → **Default Security List** → **Add Ingress Rules**.
2. Add rule: **Source CIDR `0.0.0.0/0`**, **Destination port range `80,443`**.
3. Save.

(Port 22 is open by default for SSH.)

## Step 3 — SSH in and install Docker

```bash
ssh -i ~/.ssh/education_ed25519 ubuntu@<PUBLIC_IP>

# Inside the VM:
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose-plugin git ufw curl
sudo usermod -aG docker $USER
exit  # log out so the docker group takes effect
```

Reconnect:

```bash
ssh -i ~/.ssh/education_ed25519 ubuntu@<PUBLIC_IP>
docker run hello-world  # should succeed without sudo
```

### 3.1 Add a 4 GB swap file (helps embedding model loads)

```bash
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 3.2 Host firewall (defence in depth on top of Oracle's rules)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80
sudo ufw allow 443
sudo ufw --force enable
```

## Step 4 — Set up Neon (Postgres + pgvector)

1. https://console.neon.tech → **New Project**.
2. Name: `education-prod`. Region: pick the one closest to your Oracle VM region.
3. After creation: **Dashboard → Connection Details** → copy the `postgresql://...` URL with **pooled connection** enabled.
4. **SQL Editor** → run:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

Save the connection URL — it goes into `.env` as `DATABASE_URL`.

## Step 5 — Set up Cloudflare R2 (object store)

1. https://dash.cloudflare.com → **R2** → **Create bucket**.
2. Name: `education-artefacts`.
3. **Manage R2 API Tokens** → *Create API Token* → permission **Object Read & Write** scoped to this bucket → copy **Access Key ID** and **Secret Access Key**.
4. Note the endpoint: `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`.

Save these — they go into `.env`.

## Step 6 — Set up Anthropic key

1. https://console.anthropic.com → **API Keys** → **Create Key**.
2. Copy the key (starts with `sk-ant-…`).

This goes into `.env` as `ANTHROPIC_API_KEY`.

## Step 7 — Clone the repo on the VM and configure secrets

```bash
# On the VM:
git clone https://github.com/<your-user>/education.git
cd education
cp .env.example .env
nano .env  # fill in the values from Steps 4, 5, 6
```

Required `.env` values:

```
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=postgresql://...neon.tech/...?sslmode=require
REDIS_URL=redis://redis:6379/0
S3_ENDPOINT=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
S3_BUCKET=education-artefacts
S3_ACCESS_KEY=...
S3_SECRET_KEY=...
JWT_SECRET=$(openssl rand -hex 32)
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_ANON_KEY=...
LANGFUSE_HOST=http://langfuse:3000
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
APP_DOMAIN=<vm-public-ip>.nip.io   # see Step 9
```

> Tip: `nip.io` gives you a free `*.nip.io` hostname that resolves to any IP — useful to get HTTPS without owning a domain.

## Step 8 — First boot

```bash
docker compose -f infra/docker-compose.yml up -d
docker compose -f infra/docker-compose.yml logs -f api
```

Run database migrations:

```bash
docker compose -f infra/docker-compose.yml exec api alembic upgrade head
docker compose -f infra/docker-compose.yml exec api python -m apps.api.seeds.load
```

Smoke test:

```bash
curl http://localhost:8000/healthz
# {"status":"ok","db":"ok","redis":"ok","mcp":"ok"}
```

## Step 9 — TLS with Caddy (the `nip.io` shortcut)

Add a Caddy service in `docker-compose.yml`:

```yaml
caddy:
  image: caddy:2
  ports: ["80:80", "443:443"]
  volumes:
    - ./infra/Caddyfile:/etc/caddy/Caddyfile
    - caddy_data:/data
  depends_on: [api]

volumes:
  caddy_data:
```

`infra/Caddyfile`:

```
{$APP_DOMAIN} {
    reverse_proxy api:8000
}
```

Set `APP_DOMAIN=<your-vm-ip>.nip.io` in `.env` (e.g. `137-184-22-11.nip.io`). Then:

```bash
docker compose -f infra/docker-compose.yml up -d caddy
```

Caddy auto-issues a free Let's Encrypt cert in ~30 seconds.

Test:

```bash
curl https://<your-vm-ip>.nip.io/healthz
```

Done — you have a public HTTPS API on free infra.

## Step 10 — Deploy the web client to Cloudflare Pages

1. https://dash.cloudflare.com → **Workers & Pages** → **Create → Pages → Connect to Git**.
2. Authorise GitHub, pick the `education` repo.
3. **Build settings:**
   - Framework preset: *Vite*
   - Build command: `pnpm --filter web build`
   - Build output: `apps/web/dist`
   - Root directory: leave blank
4. **Environment variables:**
   - `VITE_API_BASE_URL=https://<vm-ip>.nip.io`
   - `VITE_SUPABASE_URL=...`
   - `VITE_SUPABASE_ANON_KEY=...`
5. Click **Save and Deploy**. After ~1 minute you'll have `https://<project>.pages.dev`.

## Step 11 — GitHub Actions CI/CD

`.github/workflows/ci.yml`:

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env: { POSTGRES_PASSWORD: pw }
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready" --health-interval 5s
      redis:
        image: redis:7
        ports: ["6379:6379"]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run pytest
      - run: uv run mypy .
      - run: uv run ruff check .
```

`.github/workflows/deploy.yml` (deploys to the VM on tag `v*`):

```yaml
name: Deploy
on:
  push:
    tags: ['v*']
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: SSH deploy
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.VM_HOST }}
          username: ubuntu
          key: ${{ secrets.VM_SSH_KEY }}
          script: |
            cd ~/education
            git pull
            docker compose -f infra/docker-compose.yml up -d --build
            docker compose -f infra/docker-compose.yml exec -T api alembic upgrade head
```

GitHub repo settings → **Secrets and variables → Actions**:

- [ ] `VM_HOST` = your VM's IP
- [ ] `VM_SSH_KEY` = contents of `~/.ssh/education_ed25519` (the private key)

**Done when:** push a tag `v0.1.0` and the VM auto-updates.

## Step 12 — Keep-alive cron (prevents Oracle Always-Free reclaim)

On the VM:

```bash
(crontab -l 2>/dev/null; echo "*/5 * * * * curl -s http://localhost:8000/healthz > /dev/null") | crontab -
```

This pings every 5 minutes — enough to keep Oracle from flagging the instance idle.

## Step 13 — Self-host Langfuse (LLM tracing) on the same VM

Append to `docker-compose.yml`:

```yaml
langfuse-db:
  image: postgres:15
  environment: { POSTGRES_PASSWORD: lfpw, POSTGRES_DB: langfuse }
  volumes: [langfuse_db:/var/lib/postgresql/data]

langfuse:
  image: langfuse/langfuse:latest
  depends_on: [langfuse-db]
  environment:
    DATABASE_URL: postgresql://postgres:lfpw@langfuse-db:5432/langfuse
    NEXTAUTH_SECRET: $(openssl rand -hex 32)
    NEXTAUTH_URL: https://${APP_DOMAIN}/langfuse
  ports: ["3000:3000"]

volumes:
  langfuse_db:
```

Add to Caddyfile:

```
{$APP_DOMAIN} {
    handle_path /langfuse/* { reverse_proxy langfuse:3000 }
    reverse_proxy api:8000
}
```

Visit `https://<vm-ip>.nip.io/langfuse`, create a project, copy the keys into `.env` (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`), `docker compose up -d api`.

## Step 14 — Smoke test in production

From your laptop:

```bash
BASE=https://<vm-ip>.nip.io

curl -X POST $BASE/v1/auth/signup -d '{"email":"test@example.com","password":"…"}' -H 'content-type: application/json'
# capture the {token}

TOKEN=eyJ...
curl -X POST $BASE/v1/me/profile \
  -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"exam_id":"aws_ccp","exam_date":"2026-08-01","daily_minutes":60}'

curl -N -X POST $BASE/v1/me/topics/cloud-concepts/teach \
  -H "authorization: Bearer $TOKEN"
# you should see SSE chunks streaming the Tutor's lesson
```

If all four calls succeed and a trace shows up in Langfuse, **you are deployed.**

## Step 15 — Day-1 cost verification

- [ ] Oracle billing dashboard: only Always-Free resources used.
- [ ] Neon dashboard: storage well under 500 MB.
- [ ] Cloudflare R2: storage well under 10 GB.
- [ ] Anthropic console: usage page shows real but small numbers; set a *spend alert* at $5.
- [ ] GitHub Actions: minutes used << 2,000.

You should see **$0 across all infra** with only Anthropic ticking.

---

## Operational playbook (post-deploy)

### Logs

```bash
docker compose -f infra/docker-compose.yml logs -f api worker scheduler
```

### Restart one service

```bash
docker compose -f infra/docker-compose.yml restart api
```

### Apply a migration

```bash
docker compose -f infra/docker-compose.yml exec api alembic upgrade head
```

### Roll back a deploy

```bash
git checkout <previous-tag>
docker compose -f infra/docker-compose.yml up -d --build
```

### When Anthropic spend spikes

1. Open Langfuse → filter by `cost_usd desc` for last 24h.
2. Identify the agent + prompt.
3. Enable / verify prompt cache on that agent's system prompt.
4. Lower the per-user daily token budget in `.env`.
5. Switch the agent to Haiku if Sonnet wasn't required.

### When Neon hits 80% storage

1. Run a one-off cleanup of `analytics` table older than 30 days.
2. If still tight, upgrade to Neon Pro ($19) or migrate Postgres to the VM.

---

## Phase 11 — v0.1 acceptance test

The product is "v0.1 done" when **one engineer who has never seen the project** can:

1. Read `prd.md`, `tech-plan.md`, `tasks.md`.
2. Follow Phase 10 from a clean laptop.
3. Reach Step 14's smoke test passing.
4. Within ~90 minutes, on $0 of infra spend.

If that fails, the task is not done — fix the docs.
