# Midas — Living TODO

> **Updated:** May 6, 2026 (end of session 4)
> **Format:** Living checklist. Updated at end of every session.
> **Aligned with:**
> - The big picture → `Bot_Architecture_v2_Professional_Grade_April26_2026.html` Section 11 (8-phase migration roadmap)
> - The granular Phase 1 work → `docs/PHASE_1_PLAN.md`
>
> **Pair this with:** `docs/PROJECT_HANDOFF.html` (current state) and `docs/SESSION_HISTORY.md` (chronological session log)

---

## 🎯 Right now — Next session opens here

- [ ] **Decision: kube-prometheus-stack — Plan B vs skip.** Plan B is ~45 min of surgical work. Skipping moves us straight to Task 11. Loki + Tempo already give us 50% of LGTM, and no service depends on kps yet. Filippo + Peter pick at session start.
- [ ] **Phase 1 Task 11 — hello-svc proof-of-life** (highest value remaining task in Phase 1; see details below)

---

## 📊 Phase status at a glance

| Phase | Description | Duration estimate | Status |
|---|---|---|---|
| **Phase 0** | Keep the lights on (old bot paused) | ongoing | ✅ Active |
| **Phase 1** | Infrastructure foundation | 2-4 weeks | 🟡 In progress (9.5/12 tasks) |
| **Phase 2** | Core data layer (data, oms, pms services) | 3-4 weeks | ⚪ Pending |
| **Phase 3** | First strategy end-to-end (paper) | 2-3 weeks | ⚪ Pending |
| **Phase 4** | Go live with TIMELY only | 2-3 weeks | ⚪ Pending |
| **Phase 5** | Port remaining strategies | 3-5 weeks | ⚪ Pending |
| **Phase 6** | Hardening + MCP integration | 3-4 weeks | ⚪ Pending |
| **Phase 7** | Research & growth | ongoing | ⚪ Pending |

**Total realistic timeline: 5-6 months calendar time, evenings/weekends.**

---

## ✅ Phase 0 — Keep the lights on (ongoing)

- [x] Old Kalshi bot paused per audit synthesis
- [ ] If trading resumes during migration, do it on the OLD bot with audit fixes applied (specifically the bankroll accounting fix), NOT the half-built new system

---

## ✅ Repo bootstrap (pre-Phase 1, completed in session 1)

- [x] Create monorepo at `/Users/filippominella/midas/` (actual path: `~/Desktop/midas/`)
- [x] Set up uv workspace with `packages/bot-events/`
- [x] Build `BaseEvent` Pydantic v2 class with `ClassVar` + `__init_subclass__` enforcement
- [x] Write 5 unit tests for `BaseEvent` (all passing)
- [x] Configure ruff, pytest, Makefile (install/lint/format/test)
- [x] All quality gates green
- [x] Push to `github.com/bakerlunch-ai/midas` (private)
- [x] Authenticate `gh`, `doctl`; install kubectl
- [x] Write `docs/LESSONS_FROM_OLD_BOT.md` (10 binding constraints)
- [x] Write `docs/PHASE_1_PLAN.md` (12-task plan)
- [x] Save Claude Code feedback memory

---

## 🟡 Phase 1 — Infrastructure foundation (9.5/12 tasks complete)

> Goal: a functional empty cluster with all infrastructure running. No trading services yet. You can `kubectl apply` a hello-world service and see it appear in Grafana with logs and metrics.

- [x] **Task 1** — Provision Kubernetes cluster (DOKS, LON1, 3 × s-2vcpu-4gb)
- [x] **Task 2** — Provision managed Postgres + 3 logical DBs (oms_db, pms_db, reporting_db)
- [x] **Task 3** — Provision managed Redis (Valkey 8, smallest tier, VPC-only)
- [x] **Task 4** — Bootstrap monorepo (uv workspace, ruff, pytest, Makefile, CI)
- [x] **Task 5** — GitHub Actions CI gate (lint + test on every push)
- [x] **Task 6** — Argo CD installed and bootstrapped (GitOps loop functional)
- [x] **Task 7** — Sealed-secrets controller (round-trip verified end-to-end)
- [x] **Task 8** — Real credentials sealed (postgres-oms, postgres-pms, postgres-reporting, redis — all decoded clean, structure verified)
- [x] **Task 9** — NATS JetStream 3-replica cluster (durability tested via leader-kill recovery)
- [ ] **Task 10** — LGTM observability stack
  - [x] Loki 7.0.0 deployed and running
  - [x] Tempo 1.24.4 deployed and running
  - [ ] kube-prometheus-stack 84.5.0 — **stuck on CRD bootstrap.** Plan A failed (`SkipDryRunOnMissingResource` + `Replace` syncOptions didn't unblock). See "kps Plan B" below.
- [ ] **Task 11** — hello-svc Python proof-of-life
- [ ] **Task 12** — Phase 1 runbook (`docs/RUNBOOK.md`)

### kps Plan B — for next session

- [ ] Delete current `kube-prometheus-stack` Argo CD Application (won't delete already-installed CRDs)
- [ ] Create new `kube-prometheus-stack-crds` Application that installs **only** the CRDs from `prometheus-community/prometheus-operator-crds` chart
  - Annotation: `argocd.argoproj.io/sync-wave: "-1"` (forces install before main kps)
- [ ] Modify main `kube-prometheus-stack` Application: add `crds.enabled: false` to values block
- [ ] Apply both, watch sync wave -1 finish first
- [ ] Fallback if Plan B also fails: bypass Argo CD for this chart, install via `helm install` directly, then write a stub Argo CD Application referencing the existing release

### Task 11 — hello-svc proof-of-life (next big task)

Build a tiny FastAPI service that exercises the full Phase 1 stack:

- [ ] Create `services/hello-svc/` in the monorepo
- [ ] Single FastAPI endpoint: `GET /health` returns `{"ok": true}`
- [ ] On startup, read `DATABASE_URL` and `REDIS_URL` from env
- [ ] Connect to Postgres, run `SELECT 1`
- [ ] Connect to Redis, run `PING`
- [ ] Connect to NATS, publish `events.heartbeat.hello-svc` once a minute
- [ ] Dockerfile + container build via GitHub Actions, push to GitHub Container Registry
- [ ] Custom local Helm chart in `deploy/charts/hello-svc/`
- [ ] Argo CD Application in `deploy/applications/hello-svc.yaml`
- [ ] Reference the four sealed Secrets via `envFrom: secretRef`
- [ ] Confirm pod starts, hits all three dependencies, publishes heartbeats

This is the first piece of actual Python service code in Midas.

### Task 12 — Phase 1 runbook

- [ ] Write `docs/RUNBOOK.md`
- [ ] Section: cluster overview (what runs where, how to reach Argo CD UI)
- [ ] Section: how to seal a new credential (canonical doctl pattern from PROJECT_HANDOFF section 06)
- [ ] Section: how to deploy a new service (Application file → commit → Argo CD picks up)
- [ ] Section: common debug commands (pod logs, describe, events)
- [ ] Section: cost dashboard (where to look, what to expect)

---

## ⚪ Phase 2 — Core data layer (pending)

> Goal: the three core stateful services running. They're event-sourced, NATS-connected, and emit observability data. No trading logic yet.

- [ ] `data-svc` — fetches market data from Kalshi (and later Polymarket), publishes `events.market.*` to NATS
- [ ] `oms-svc` — Order Management Service. Owns the order lifecycle, talks to broker APIs, emits `events.order.*`
- [ ] `pms-svc` — Position Management Service. Tracks positions, computes risk metrics, emits `events.position.*`
- [ ] Schema versioning enforced via Pydantic + JSON Schema for every event type
- [ ] Reconciliation jobs scheduled (CronJob), reading from `events.*` to rebuild state from scratch
- [ ] Smoke test: data-svc emits a fake market tick → oms-svc reacts (logs only) → pms-svc updates position estimate → reporting_db row appears
- [ ] All three services have ServiceMonitor objects (once kps is fixed)

---

## ⚪ Phase 3 — First strategy end-to-end (paper, pending)

- [ ] Pick TIMELY (highest legacy win-rate) as the first strategy to port
- [ ] Build `strategy-svc` skeleton: subscribes to market events, applies strategy logic, publishes `events.signal.*`
- [ ] Risk gate as a single canonical implementation (constraint #5)
- [ ] Paper environment: orders go to a fake-broker that records but doesn't transmit
- [ ] End-to-end smoke: market tick → strategy fires signal → risk gate evaluates → fake order written → position updated → P&L row appears
- [ ] Backtest harness reads historical events from JetStream and replays through the same code path

---

## ⚪ Phase 4 — Go live with TIMELY only (pending)

- [ ] Switch fake-broker to real Kalshi API in `oms-svc` config
- [ ] Hard daily loss limit enforced (one canonical implementation in risk-svc)
- [ ] Paper bot runs in parallel for confidence comparison
- [ ] Reconciliation jobs verified against actual broker statements
- [ ] Pager rules + alerting through Alertmanager (once kps is fixed)
- [ ] First real trade. Eyes on dashboards.

---

## ⚪ Phases 5-7 — Port strategies, harden, research

(Detailed checklists added once we're closer; per architecture v2 Section 11)

---

## 📌 Active carry items (not blocking immediate work)

- [ ] **Password manager upgrade.** Filippo's credentials currently in a Word doc on Desktop. Move to 1Password or Bitwarden before Phase 2 services start touching production data. Filed during session 3.
- [ ] **App-of-Apps pattern.** Defer until ~10 Argo CD Applications exist and managing them individually feels painful.
- [ ] **NATS Application showing OutOfSync in Argo CD.** Pods are healthy and serving traffic — this is cosmetic drift. Investigate when convenient.
- [ ] **Postgres user password rotation (defense-in-depth).** Host fragment was leaked in chat May 6. VPC-only access plus password requirements mean no exploitable risk. Optional, not urgent.
- [ ] **metrics-server.** `kubectl top nodes` currently fails because metrics-server isn't installed. kps will provide richer metrics once running. If kps stays deferred, install metrics-server separately.
- [ ] **Re-verify postgres-oms.yaml works at runtime.** Sealed file decoded clean structurally, but no service has actually used it to connect yet. Task 11 will exercise this.

---

## 🧰 Working agreement reminders (codified in PROJECT_HANDOFF.html section 10)

1. **Credential sealing canonical pattern: doctl, never the DO web UI copy buttons.** See PROJECT_HANDOFF section 06.
2. **Verify each sealed file before moving on** — apply, decode, check structure (`@` visible, single line, password present).
3. **3-hour cap on credential-handling sessions.** After that, save state and resume next session.
4. **Never `cat | pbcopy` sensitive files.** Use `open -a TextEdit` for GUI access.
5. **Sed regex for diagnostic redaction:** `[A-Za-z0-9!#$%^&*()_+=-]\{6,\}` — exclude `@` so URL structure stays visible.
6. **Pin Helm chart versions, no moving tags.** Verify current with `helm search repo` before pinning.
7. **Argo CD prune-on-app-delete doesn't always cascade.** Pattern: remove files from git → let Argo CD prune → then delete the Application.

---

## 🚦 Gate to next phase

Phase 1 is complete when:
- [ ] All 12 Task checkboxes above are checked
- [ ] hello-svc visible in Grafana with logs (Loki) and metrics (kps once fixed) — or equivalent visibility if kps stays deferred
- [ ] PROJECT_HANDOFF.html section 03 shows zero `Degraded` Applications
- [ ] Runbook is written and shippable to a teammate who's never touched the cluster

When that's true → Phase 2 begins. The first piece of actual trading-adjacent code lands.
