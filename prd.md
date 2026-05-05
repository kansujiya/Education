# PRD — Education AI: Exam Prep Companion

> Status: Draft v0.1 · Owner: Education AI team · Last updated: 2026-05-05

## 1. Overview

**Education AI** is an agentic AI exam-preparation companion that takes a candidate from the day they decide to sit an exam to the day they walk into the hall — and beyond, to results. Unlike content-delivery apps, the system behaves like a private coach: it adapts to the candidate's level, drills weak areas, grounds every drill in real past-year questions (PYQs), and shows the candidate where they stand against the historical bar for clearing the exam.

**One-line pitch:** an agentic AI tutor that takes a candidate from syllabus to selection.

**North-star outcome:** **selection rate of users who complete a journey** — not hours studied, not topics covered.

## 2. Problem Statement

Self-prep candidates consistently fail at four things:

1. **Prioritisation.** They study what's easy or first, not what's high-yield.
2. **Retention.** Linear reading does not stick; weeks later the topic is gone.
3. **Calibration.** They don't know if their level matches what the exam actually demands.
4. **Pacing.** Without a coach, the schedule drifts and crunch-time panic sets in.

Existing apps push content (videos, PDFs, mock tests) but do not behave like a coach who watches the candidate, adapts daily, and pulls them toward selection. Agentic AI changes this: a system of cooperating agents can teach, examine, drill, track, and re-plan in a loop that mirrors real coaching.

## 3. Target Users & Personas

v1 supports **multi-user accounts** with isolated profiles and progress.

### Primary persona — Aarav, 22, "The Self-Prep Aspirant"
- **Context:** Final-year engineering student preparing for GATE in 9 months while attending college.
- **Device:** Phone primarily, laptop on weekends.
- **Daily budget:** 2 hours weekdays, 5 hours weekends.
- **Goals:** Cover the syllabus end-to-end, peak in the last 30 days, clear the cutoff for his target college.
- **Pain points:** Gets lost in YouTube playlists; doesn't know which topics carry the most marks; forgets formulas a week after revising; no honest feedback on whether he's on track.
- **Quote:** *"I don't need more content. I need someone to tell me what to do today and whether it's enough."*
- **What success looks like for Aarav:** Daily 90-min plan he actually finishes, weekly readiness score that climbs, mock-test performance matching predicted readiness within ±5%.

### Primary persona — Priya, 27, "The Working Professional Switcher"
- **Context:** Software engineer prepping for UPSC Civil Services after work; weekends are sacred study time.
- **Device:** Laptop on weekends, phone for revision during commute.
- **Daily budget:** 1 hour weekdays (commute), 6 hours weekends.
- **Goals:** Build conceptual depth in unfamiliar subjects (history, polity); use commute for spaced revision; track readiness honestly so she knows when to take leave for the final push.
- **Pain points:** Gigantic syllabus; can't tell signal from noise; revision drops off; expensive coaching she can't attend live.
- **Quote:** *"I'd pay for something that respects my 60 minutes and tells me exactly what to revise on the train."*
- **What success looks like for Priya:** Offline-downloadable topic packs; mind maps she can scan in 5 minutes; PYQ-grounded drills that prove she'd have answered last year's paper.

### Primary persona — Karthik, 19, "The First-Attempt Repeater"
- **Context:** Took NEET once, missed cutoff by 30 marks, attempting again. Lives at home, full-time prep.
- **Device:** Tablet + phone.
- **Daily budget:** 8 hours.
- **Goals:** Diagnose what specifically broke last time, fix gaps, build exam temperament.
- **Pain points:** Demotivation, no honest gap analysis, repeating same mistakes, weak topics he avoids.
- **Quote:** *"I studied a lot last year. I still failed. I need to know what was actually wrong."*
- **What success looks like for Karthik:** Diagnostic onboarding that pinpoints weak topics; the system refusing to let him skip those; visible weekly improvement on PYQ-derived drills.

### Secondary persona — Meera, 45, "The Concerned Parent" (post-v1)
- **Context:** Parent of a JEE aspirant; pays for prep; wants visibility, not control.
- **Goals:** See progress without micromanaging the candidate.
- **v1 implication:** Account model and progress data must support a future read-only "guardian view." No build in v1, but data model should not block it.

### Secondary persona — Coaching Institute Admin (post-v1)
- **Context:** Small institute wants to offer this to their batch.
- **v1 implication:** Multi-tenancy is not in v1, but auth and account scoping should leave room for an "organisation" entity later.

### Anti-persona — Casual browsers
This product is **not** for users without a target exam and date. The journey starts with a committed candidate. Casual learners are an explicit non-user.

### Persona-driven design implications
- **Mobile-first feel** even though web ships first (Aarav, Priya commute, Karthik tablet).
- **Offline-capable downloads** are a v1 requirement, not a nice-to-have (Priya's commute, exam-day no-wifi halls).
- **Honest diagnostic** must exist by v1 (Karthik will not trust the system without it).
- **Time-budget awareness** in the planner is mandatory (Aarav and Priya have very different budgets).
- **Guardian / institute hooks** stay out of v1 scope but informs the data model.

## 4. Goals & Non-Goals

### Goals (v1)
- Outcome-oriented coaching (clear the exam, not just study).
- Layman-language teaching for every topic.
- Auto-generated mind maps for retention.
- Active recall via card-based assessments.
- All assessments grounded in real PYQs.
- Historical exam insights (cutoffs, selection %, topic-frequency heatmap).
- Progress tracking with predicted readiness.
- Per-topic downloadable bundle for offline access.
- Multi-user accounts with isolated progress.
- API-first architecture so mobile + web can plug in.

### Non-Goals (v1)
- Live human tutors.
- Video lectures.
- Payments / subscriptions.
- Social or community features.
- Proctored mock-exam infrastructure.
- Content for exams without an ingestable syllabus + PYQ corpus.

## 5. User Journey

1. **Onboarding** — sign up, pick exam, set exam date, set daily study budget, optional diagnostic.
2. **Syllabus surfacing** — Syllabus Agent fetches/parses the syllabus for the chosen exam, presents a structured tree (subject → unit → topic).
3. **Plan generation** — Coach Agent builds a date-aware study plan, weighted by PYQ frequency and the user's confidence + diagnostic results.
4. **Topic learning loop** (per topic):
   1. **Teach** — Tutor Agent gives a layman explanation tuned to the user's level (analogy + real-world example + 3-line summary).
   2. **Mind-map** — auto-generated visual mind map for retention.
   3. **Interactive session** — Examiner Agent runs Socratic Q&A; user can ask back; ends only on explicit "understood."
   4. **Card-based assessment** — Assessor Agent issues spaced-repetition flashcards + PYQ-derived MCQs.
   5. **Mastery gate** — topic flips to "prepared" only when assessment threshold is met.
5. **Historical insight panel** — per topic and on dashboard: PYQ frequency, past cutoffs, selection percentile trend, weight in last N years.
6. **Progress tracking** — dashboard with topics done, mastery %, days to exam, projected readiness.
7. **Download & offline access** — per-topic export (notes + mind map + cards) as PDF / markdown ZIP, accessible anytime.
8. **Revision mode** — auto-activates near exam date (default: 14 days out); switches to drills on weakest cards + high-yield PYQs.

## 6. Functional Requirements

| ID | Requirement |
|----|-------------|
| FR-1 | **Account.** Email/OTP signup; profile stores exam, exam date, daily minutes, optional diagnostic score. |
| FR-2 | **Exam catalog.** New exams added via syllabus + PYQ ingestion (admin or agent-assisted). |
| FR-3 | **Syllabus view.** Hierarchical, searchable; per-topic status (not started / in progress / mastered). |
| FR-4 | **Adaptive study plan.** Regenerates when user falls behind, exam date changes, or weak areas emerge. |
| FR-5 | **Layman teaching.** Explanation includes analogy, real-world example, and a 3-line summary. |
| FR-6 | **Mind map.** Generated as a structured node tree; rendered client-side. |
| FR-7 | **Interactive session.** Agent asks ≥3 comprehension questions; user can ask back; ends with explicit "understood." |
| FR-8 | **Card assessment.** Mix of recall (flip), MCQ (PYQ-grounded), and short-answer; spaced-repetition scheduling. |
| FR-9 | **PYQ grounding.** Every assessment item tagged with source year/section when derived from a PYQ. |
| FR-10 | **Historical insight.** Per exam: last-N-years cutoffs, selection %, topic-frequency heatmap. |
| FR-11 | **Progress dashboard.** Mastery %, time invested, predicted readiness, weak-topic list. |
| FR-12 | **Download.** Per-topic bundle (notes + mind map + cards) as PDF and markdown ZIP. |
| FR-13 | **Revision mode.** Auto-activates at configurable days-before-exam (default 14). |
| FR-14 | **Multi-user isolation.** All progress, downloads, and generated artefacts scoped to user account. |
| FR-15 | **API-first.** All capabilities exposed via versioned HTTP API; mobile + web are clients of the same API. |

## 7. Agent Architecture (product view)

The system is a cooperative multi-agent setup. Framework choice is intentionally deferred to the technical plan; the PRD only fixes the *roles*:

- **Onboarding Agent** — collects exam, date, level, diagnostic.
- **Syllabus Agent** — fetches/parses syllabus, maintains topic tree.
- **Coach Agent** — owns the study plan and re-planning.
- **Tutor Agent** — teaches each topic in layman terms; generates mind map.
- **Examiner Agent** — runs interactive Q&A; decides comprehension.
- **Assessor Agent** — generates and grades cards; manages spaced repetition.
- **Insight Agent** — surfaces historical exam data and PYQ patterns.
- **Progress Agent** — tracks mastery; predicts readiness.
- **Export Agent** — packages downloadable topic bundles.

## 8. Data the system needs

- **Exam catalog:** syllabus tree, PYQ corpus (with year/section tags), cutoffs, selection % history.
- **User state:** profile, plan, progress, spaced-repetition state, diagnostic results.
- **Generated artefacts:** notes, mind maps, cards — cached per topic per user.

## 9. Success Metrics

- **Outcome (north-star):** % of journey-completing users who self-report clearing the exam (post-exam survey).
- **Engagement:** topics mastered per active week.
- **Retention:** day-7 / day-30 retention; % of plan completed before exam date.
- **Quality:** average assessment score on PYQ-derived items; thumbs-up rate per teach session.
- **Trust:** % of historical-insight panels viewed without "report inaccuracy" clicks.

## 10. Risks & Open Questions

- Sourcing accurate, up-to-date syllabus + PYQs for arbitrary exams (legal, freshness).
- Hallucination on historical stats — every number must be cited or flagged "AI-estimated."
- Mind-map rendering on mobile (size, interaction).
- Latency / cost of multi-agent loops per topic — needs caching and partial-prompt reuse.
- How to verify "understood" without becoming annoying.
- Cold-start for an exam with no PYQ corpus yet.

## 11. Release Plan

- **v0.1 (learning slice):** single hardcoded exam, CLI/API only, full topic-learning loop end-to-end. Goal: prove the agent flow.
- **v1.0:** multi-user web app, generic exam onboarding, downloads, historical insights.
- **v1.1:** mobile app (React Native or Flutter), offline pack, revision-mode polish.
- **post-v1:** guardian view, institute multi-tenancy, payments.

## 12. Out of Scope (explicit)

Live tutors, video lectures, payments, community features, proctored mocks, certificate issuance, content for exams without an ingestable syllabus + PYQ corpus.
