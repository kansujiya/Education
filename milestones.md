# Milestones — Education AI v0.1

> Companion to `prd.md`, `tech-plan.md`, `tasks.md`, `backlog.md`. Status: Draft v0.1 · Last updated: 2026-05-05

`backlog.md` lists work item-by-item (109 tickets across 14 epics). This document re-cuts the same work into **11 milestones**, where each milestone delivers:

- one **end-to-end demoable outcome** (a real thing a human can see working),
- one **literal demo script** (commands to copy-paste),
- the **tests** that lock the demo down so it can't silently regress.

Milestones are vertical slices, not horizontal layers. Working software ships at every step — not "all models, then all agents, then all APIs."

---

## How to read this

```
## M-N — <Theme> · "<Title>"
Outcome:       What now works that didn't before
Demo script:   Literal commands a reviewer runs
Tests added:   Specific test files / IDs
Tickets:       From backlog.md
Done when:     Hard acceptance check
Est:           Calendar time (solo)
```

A milestone is **done** only when (a) the demo runs green from a clean checkout, and (b) the tests in that milestone are added to CI and pass. No milestone is "almost done."

---

## M-0 — Foundations · "Hello, agent"

**Outcome.** One Claude-powered agent answers a fixed prompt over the CLI, with prompt caching wired and a Langfuse trace visible. Repo, CI, and lint baseline are in place.

**Demo script.**
```bash
make dev                                 # docker compose: postgres, redis, langfuse
uv run python -m apps.api.cli ask "Explain mutex in one paragraph"
# → streams a Sonnet response
# → on second identical call, console reports >80% input-token cache hit
open http://localhost:3000               # Langfuse trace visible
```

**Tests added.**
- `tests/unit/test_base_agent.py::test_echo_agent_returns_text`
- `tests/unit/test_base_agent.py::test_prompt_cache_hit_on_second_call`
- `tests/unit/test_token_accounting.py::test_cost_usd_recorded`
- `make lint` and `make typecheck` green in CI.

**Tickets.** T-001…T-008, T-010, T-040…T-044, T-048.

**Done when.** A first-time visitor runs `make dev && uv run python -m apps.api.cli ask "..."` and sees a streamed response + a Langfuse trace within 10 minutes of clone.

**Est.** ~2 days.

---

## M-1 — Persistence + first MCP · "Syllabus loader"

**Outcome.** A CLI command pulls the AWS CCP syllabus through `mcp-syllabus`, parses it, and writes a topic tree into Postgres. Multi-user repository scoping is enforced from the start.

**Demo script.**
```bash
make seed
uv run python -m apps.api.cli load-exam aws-ccp
uv run python -m apps.api.cli show-syllabus aws-ccp --user u_demo
# → prints a topic tree
```

**Tests added.**
- `tests/integration/test_mcp_syllabus.py::test_fetch_and_parse_round_trip`
- `tests/integration/test_repo_scoping.py::test_user_a_cannot_read_user_b`
- Migrations applied + reversed cleanly in CI.

**Tickets.** T-011, T-012, T-016, T-017 (partial), T-020…T-027, T-045, T-046, T-050.

**Done when.** Topic tree round-trips cleanly through MCP → DB → CLI; cross-user reads are blocked.

**Est.** ~2 days.

---

## M-2 — Teach one topic · "Tutor + mind map, streamed"

**Outcome.** Tutor Agent teaches one topic in layman language with a Mermaid mind map, streamed to the CLI. RAG `notes_index` is live with seeded notes.

**Demo script.**
```bash
uv run python -m apps.api.cli teach \
  --user u_demo --exam aws-ccp --topic cloud-concepts
# → lesson streams chunk-by-chunk
# → mind map SVG written to ./out/mindmap.svg
open ./out/mindmap.svg
```

**Tests added.**
- `tests/eval/test_tutor_groundedness.py::test_lesson_grounded_in_retrieved_notes` (pass threshold ≥ 0.8 on a 10-prompt eval set; gates CI).
- `tests/integration/test_mcp_mindmap.py::test_renders_valid_svg`
- `tests/integration/test_rag_notes.py::test_recall_at_5_above_threshold`

**Tickets.** T-013, T-024, T-052, T-060, T-062, T-063, T-073.

**Done when.** Lesson + mind map for any seeded topic is reproducible across two consecutive runs (cache hit) and grounded in cited notes.

**Est.** ~3 days.

---

## M-3 — Verify understanding · "Examiner Socratic loop"

**Outcome.** After Tutor finishes, Examiner asks ≥3 comprehension questions, judges answers, and either passes the user (`topic.understood` event) or loops back to Tutor with the gap noted (capped at 3 iterations).

**Demo script.**
```bash
uv run python -m apps.api.cli teach --user u_demo --topic cloud-concepts \
  --interactive
# → after lesson, 3 questions appear
# → answer in stdin
# → on pass: prints "Understood ✓"; emits topic.understood on Redis Streams
xadd-tail education:events  # tiny helper that prints stream tail
```

**Tests added.**
- `tests/eval/test_examiner_judge.py::test_judge_precision_above_threshold` (precision ≥ 0.85 on labelled answers).
- `tests/integration/test_evaluator_optimiser_loop.py::test_loop_caps_at_three`
- `tests/integration/test_event_emit.py::test_topic_understood_lands_on_stream`

**Tickets.** T-014, T-016, T-074, T-080.

**Done when.** Loop demonstrably re-teaches on a wrong answer once, then passes; events visible on the bus.

**Est.** ~2 days.

---

## M-4 — Drill and progress · "PYQ-grounded cards + mastery"

**Outcome.** Assessor issues 6 PYQ-grounded cards, the user attempts them, listeners update mastery and schedule spaced repetition, and `topic.mastered` fires when the threshold is crossed.

**Demo script.**
```bash
uv run python -m apps.api.cli cards --user u_demo --topic cloud-concepts
# → 6 cards print, each citing a PYQ year/section
uv run python -m apps.api.cli attempt --card c_001 --answer "..."
# → score returned; SR due_at set; mastery updated
uv run python -m apps.api.cli progress --user u_demo
# → mastery %, days-to-exam, weak topics
```

**Tests added.**
- `tests/eval/test_assessor_card_quality.py` (≥ 80% of cards are answerable from the lesson + PYQ corpus).
- `tests/integration/test_listeners.py::test_progress_updater_recomputes_mastery`
- `tests/integration/test_listeners.py::test_spaced_rep_scheduler_sets_due_at`
- `tests/integration/test_listeners.py::test_topic_mastered_fires_at_threshold`

**Tickets.** T-014, T-015, T-051, T-061, T-075, T-077, T-081, T-082, T-086.

**Done when.** Mastery for a topic visibly climbs from 0 → ≥ 80% over a successful attempt sequence; one card is rescheduled for SR.

**Est.** ~3 days.

---

## M-5 — Plan the journey · "Coach + onboarding"

**Outcome.** Onboarding writes a profile; Coach builds a 7-day plan weighted by PYQ frequency; on a `progress`-triggered signal, the plan replans.

**Demo script.**
```bash
uv run python -m apps.api.cli onboard --user u_demo \
  --exam aws-ccp --exam-date 2026-08-01 --daily-minutes 60
uv run python -m apps.api.cli plan --user u_demo
# → 7-day plan with topics ordered by PYQ weight × confidence
uv run python -m apps.api.cli simulate-fall-behind --user u_demo
# → plan.replan emitted; new plan written
uv run python -m apps.api.cli plan --user u_demo
# → updated schedule
```

**Tests added.**
- `tests/integration/test_coach_plan.py::test_plan_orders_by_pyq_weight`
- `tests/integration/test_coach_plan.py::test_replan_on_signal`
- `tests/eval/test_coach_planning.py::test_plan_fits_daily_budget`

**Tickets.** T-070, T-072, T-079, T-083.

**Done when.** A user with `aws-ccp` and 9-month exam window receives a sensible plan; replan changes the plan deterministically when behind.

**Est.** ~2 days.

---

## M-6 — Outcome focus · "Insights + downloadable bundle"

**Outcome.** Insight panel returns cutoffs, selection %, topic heatmap, with provenance; Export packages a topic into a PDF + markdown ZIP, stored in the object store, retrievable via pre-signed URL.

**Demo script.**
```bash
uv run python -m apps.api.cli insight --exam aws-ccp --topic cloud-concepts
# → cutoffs, selection %, heatmap (with year-tagged citations)
uv run python -m apps.api.cli export --user u_demo --topic cloud-concepts
# → returns a pre-signed URL
curl -L "<url>" -o cloud-concepts.zip
unzip -l cloud-concepts.zip   # notes.md, mindmap.svg, cards.json
```

**Tests added.**
- `tests/integration/test_insight.py::test_returns_provenance_for_every_number`
- `tests/integration/test_export_bundle.py::test_bundle_contains_lesson_mindmap_cards`
- `tests/integration/test_export_bundle.py::test_presigned_url_is_downloadable`

**Tickets.** T-053, T-054, T-076, T-078, T-087.

**Done when.** Bundle opens correctly on a different machine; insight numbers always show their year/source.

**Est.** ~2 days.

---

## M-7 — Multi-user API · "End-to-end via HTTP"

**Outcome.** FastAPI with JWT auth, rate limiting, and the full v1 endpoint set. Two real users can run the journey concurrently in isolation. SSE streams Tutor + Examiner.

**Demo script.**
```bash
make dev
BASE=http://localhost:8000
TOKEN_A=$(curl -s -X POST $BASE/v1/auth/signup -H 'content-type: application/json' \
  -d '{"email":"a@x.com","password":"…"}' | jq -r .token)
TOKEN_B=$(curl -s -X POST $BASE/v1/auth/signup -H 'content-type: application/json' \
  -d '{"email":"b@x.com","password":"…"}' | jq -r .token)

curl -s -X POST $BASE/v1/me/profile -H "authorization: Bearer $TOKEN_A" \
  -d '{"exam_id":"aws-ccp","exam_date":"2026-08-01","daily_minutes":60}'
curl -N -X POST $BASE/v1/me/topics/cloud-concepts/teach \
  -H "authorization: Bearer $TOKEN_A"   # SSE stream for user A

curl -s $BASE/v1/me/progress -H "authorization: Bearer $TOKEN_B" | jq
# → empty for B; A's progress not visible
```

**Tests added.**
- `tests/e2e/test_full_journey_api.py::test_user_signup_to_export`
- `tests/e2e/test_isolation.py::test_user_a_cannot_see_user_b`
- `tests/e2e/test_rate_limit.py::test_burst_returns_429`
- `tests/e2e/test_sse.py::test_teach_streams_chunks`

**Tickets.** T-026, T-088, T-090…T-100.

**Done when.** Both demo scripts above and the four e2e tests are green in CI against an ephemeral compose stack.

**Est.** ~4 days.

---

## M-8 — Web demo · "Browser walkthrough"

**Outcome.** Web client serves the full user journey: signup → onboarding → topic learning (live SSE + Mermaid render) → cards → progress → download.

**Demo script.**
```bash
make web-dev
open http://localhost:5173
# Click through: signup → onboarding → today's plan → "Learn cloud-concepts"
# → see Tutor lesson stream, mind map render
# → 3 comprehension Qs
# → 6 cards
# → progress dashboard updates
# → "Download topic" → bundle saved locally
```

**Tests added.**
- `tests/e2e-web/journey.spec.ts` (Playwright): full happy path.
- `tests/e2e-web/insight_panel.spec.ts`: cutoffs + heatmap + provenance render.
- `tests/e2e-web/lighthouse.spec.ts`: a11y ≥ 90.

**Tickets.** T-100, T-110…T-118.

**Done when.** Playwright runs green in CI on a clean checkout; Lighthouse a11y ≥ 90.

**Est.** ~4 days.

---

## M-9 — Free-tier production deploy · "Public URL, $0 infra"

**Outcome.** Live on Oracle Always-Free VM + Neon + Cloudflare R2 + Pages, with TLS via Caddy + nip.io, GitHub Actions tag-based deploy, keep-alive cron, and self-hosted Langfuse.

**Demo script.**
```bash
# From a different laptop:
BASE=https://<vm-ip>.nip.io
curl $BASE/healthz
curl -X POST $BASE/v1/auth/signup ...    # full journey works
open https://<project>.pages.dev          # web client live
```

**Tests added.**
- `tests/prod-smoke/test_smoke.sh` runs the demo script and asserts 200s + a Langfuse trace appears.
- Cost-dashboard checks (`tools/check_dashboards.sh`) print Oracle / Neon / R2 / Pages dashboards all at $0.
- Tag-deploy workflow gated by all CI tests passing.

**Tickets.** T-120…T-130, T-118.

**Done when.** External smoke test green; cost dashboards confirm $0 infra; one Anthropic spend alert configured.

**Est.** ~1 day.

---

## M-10 — Hardening · "Observability, security, evals"

**Outcome.** OTel traces span the whole forest (API → orchestrator → agents → tools/MCP/RAG); Grafana + Sentry wired; agent regression evals committed and gating CI; load test passes; security and a11y baseline locked.

**Demo script.**
```bash
# Generate one user journey end-to-end on prod
# Then:
open https://<vm-ip>.nip.io/langfuse      # forest with parent/child A2A links
open <grafana-cloud-dashboard>             # RPS, p95, agent run time, cost/user/day
open <sentry-issues>                       # zero open issues post-fix

uv run pytest tests/eval -q                 # regression evals green
uv run python tools/loadtest.py 10           # 10 concurrent users; p95 < 5s
```

**Tests added.**
- `tests/eval/*` — Tutor groundedness, Examiner judge precision, Assessor card quality, Coach plan correctness — all gated in CI.
- `tests/security/test_isolation_negative.py`
- `tests/perf/test_load_10_users.py`

**Tickets.** T-140…T-145, T-150…T-154.

**Done when.** All eval scores ≥ committed thresholds; Grafana + Sentry alerts wired; load test green.

**Est.** ~3 days.

---

## M-11 — v0.1 acceptance · "Fresh engineer, 90 minutes"

**Outcome.** A new engineer who has never seen the project follows `tasks.md` Phase 10 from a blank laptop and reaches a green production smoke test in ≤ 90 minutes at $0 infra spend.

**Demo script.** A scheduled exercise — done with a real volunteer:
```
1. Hand them the repo URL.
2. Start a 90-minute timer.
3. They follow tasks.md Phase 10.
4. They run the smoke test from their machine.
5. We check Oracle/Neon/R2 dashboards = $0.
```

**Tests added.**
- `docs/runbook-acceptance.md` — checklist filled in by the volunteer.
- `tools/check_dashboards.sh` — programmatic $0 verification.

**Tickets.** T-155.

**Done when.** Timer stops on green smoke test ≤ 90 min, dashboards $0. **This is what makes v0.1 real, not the code.**

**Est.** ~0.5 day (plus the volunteer's 90 min).

---

## Summary

| # | Theme | Demo highlight | Calendar |
|---|-------|----------------|----------|
| M-0  | Hello, agent             | CLI ask + cache hit + Langfuse trace             | 2 d |
| M-1  | Syllabus loader          | CLI loads AWS CCP syllabus via MCP                | 2 d |
| M-2  | Tutor + mind map         | CLI streams lesson + Mermaid SVG                  | 3 d |
| M-3  | Examiner loop            | 3 Socratic Qs; loop on miss; topic.understood     | 2 d |
| M-4  | Cards + mastery          | 6 PYQ-grounded cards; mastery climbs              | 3 d |
| M-5  | Coach plan               | 7-day plan with PYQ weighting; replan             | 2 d |
| M-6  | Insights + bundle        | Heatmap + downloadable PDF bundle                 | 2 d |
| M-7  | API end-to-end           | curl full journey, two-user isolation, SSE        | 4 d |
| M-8  | Web demo                 | Browser walkthrough with Mermaid + cards          | 4 d |
| M-9  | Free-tier production     | Public URL on Oracle + Neon + R2 + Pages, $0      | 1 d |
| M-10 | Hardening                | Full trace forest, evals locked, load passes      | 3 d |
| M-11 | v0.1 acceptance          | Volunteer hits green smoke test in 90 min         | 0.5 d |
| **Total** |                         |                                                | **~28.5 days (~6 weeks solo)** |

## Sequencing rules

- **No skipping.** Each milestone gates the next.
- **No "almost done."** A milestone is closed only when (a) demo is reproducible from clean clone, (b) tests in that milestone are committed and green in CI.
- **Demos are recorded.** Save a 60-second screencast or terminal recording per milestone in `docs/demos/`. They become a visible progress trail and double as bug repros if something regresses.
- **CI grows with the milestones.** A test added in M-2 must still pass at M-11. Regressions block the next milestone.

## Mapping back to other docs

- **What to build:** see `prd.md`.
- **How it's architected:** see `tech-plan.md`.
- **Step-by-step deployment:** see `tasks.md` Phase 10.
- **Ticket-level detail:** see `backlog.md` (each milestone references the tickets it consumes).
