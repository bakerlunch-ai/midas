# Midas — Living TODO

> **Updated:** May 9, 2026 (end of session 5)
> **Format:** Living checklist. Updated at end of every session.
> **Aligned with:**
> - The big picture → `Bot_Architecture_v2_Professional_Grade_April26_2026.html` Section 11 (8-phase migration roadmap)
> - The granular Phase 1 work → `docs/PHASE_1_PLAN.md`
> **Pair this with:** `docs/PROJECT_HANDOFF.html` (current state), `docs/JOURNEY.md` (narrative arc), `docs/SESSION_HISTORY.md` (chronological log)

---

## 🎯 Right now — Next session opens here

- [ ] **Phase 1 Task 12** — Document the runbook. How to deploy a new service, rotate credentials, respond to incidents, roll back. One short session. Closes Phase 1.
- [ ] After Task 12 lands: declare Phase 1 done, start Phase 2 planning (data-svc, oms-svc, pms-svc, fleshed-out bot-events package).

---

## 📊 Phase status at a glance

| Phase | Description | v2 ref | Duration estimate | Status |
|---|---|---|---|---|
| **Phase 0** | Keep the lights on (old bot paused) | §11 P0 | ongoing | ✅ Active |
| **Phase 1** | Infrastructure foundation | §05–§10 | 2-4 weeks | 🟡 In progress (**11/12 tasks**) |
| **Phase 2** | Core data layer (data, oms, pms services) | §02, §03, §04, §06 | 3-4 weeks | ⚪ Pending |
| **Phase 3** | First strategy end-to-end (paper) | §02, §11 P3 | 2-3 weeks | ⚪ Pending |
| **Phase 4** | Go live with TIMELY only | §10, §11 P4 | 2-3 weeks | ⚪ Pending |
| **Phase 5** | Port remaining strategies | §11 P5 | 3-5 weeks | ⚪ Pending |
| **Phase 6** | Hardening + MCP integration | §13, §14 | 3-4 weeks | ⚪ Pending |
| **Phase 7** | Research & growth | §11 P7 | ongoing | ⚪ Pending |

**Total realistic timeline: 5-6 months calendar time, evenings/weekends.**

---

## ✅ Phase 0 — Keep the lights on (ongoing)

- [x] Old Kalshi bot paused per audit synthesis
- [ ] If trading resumes during migration, do it on the OLD bot with audit fixes applied (specifically the bankroll accounting fix), NOT the half-built new system

---

## ✅ Repo bootstrap (pre-Phase 1, completed in session 1)

- [x] Create monorepo at `~/code/midas/` (Peter) / `~/Desktop/midas/` (Filippo)
- [x] Set up uv workspace with `packages/bot-events/`
- [x] Build `BaseEvent` Pydantic v2 class with `ClassVar` + `__init_subclass__` enforcement
- [x] Write 5 unit tests for `BaseEvent` (all passing)
- [x] Configure ruff, pytest, Makefile (install/lint/format/test)
- [x] All quality gates green
- [x] Push to `github.com/bakerlunch-ai/midas` (private)
- [x] Authenticate `gh`, `doctl`; install kubectl
- [x] Write `docs/LESSONS_FROM_OLD_BOT.md` (10 binding constraints)
- [x] Write `docs/PHASE_1_PLAN.md` (12-task plan)

---

## 🟡 Phase 1 — Infrastructure foundation (11/12 tasks complete) → v2 §05–§10

> Goal: a functional empty cluster with all infrastructure running. A real Python service can be deployed, hit DBs, publish events, be observed. Phase 1 is one task short of done.

### ✅ Task 1 — Kubernetes cluster (DONE) → v2 §05

### ✅ Task 2 — Managed PostgreSQL (DONE) → v2 §06
- [ ] Cross-DB denial check (oms_user → pms_db should fail) — **deferred to Phase 2** when service permissions are wired

### ✅ Task 3 — Managed Redis (DONE) → v2 §06

### ✅ Task 4 — GitHub Actions CI (DONE) → v2 §10

### ✅ Task 5 — Decided on in-tree manifests (DONE) → v2 §09

### ✅ Task 6 — Argo CD installed (DONE) → v2 §09

### ✅ Task 7 — Sealed-secrets controller (DONE) → v2 §09

### ✅ Task 8 — Credentials in sealed-secrets (DONE) → v2 §09
- [x] postgres-oms, postgres-pms, postgres-reporting, redis sealed for default namespace (sessions 3-4)
- [x] postgres-oms + redis re-sealed for hello-svc namespace (session 5)

### ✅ Task 9 — NATS JetStream (DONE) → v2 §07
- Deployed via Argo CD in session 4. App shows OutOfSync (cosmetic, deferred).

### ✅ Task 10 — LGTM observability stack (DONE) → v2 §08
- kube-prometheus-stack 84.5.0, Loki 7.0.0, Tempo deployed via Argo CD in session 4.

### ✅ Task 11 — Hello-world end-to-end deploy (DONE in session 5) → v2 §02, §05–§10

> **The integration test for all of Phase 1.** A real Python service that exercises every piece: cluster, image registry, GitOps, sealed-secrets, Postgres, Redis, NATS, observability.

- [x] HeartbeatEvent class added to bot-events with 7 tests
- [x] hello-svc scaffolded as uv workspace member with FastAPI `/health` endpoint
- [x] NATS heartbeat publisher (`publish_heartbeat`) wired to `events.heartbeat.<service_name>`
- [x] Postgres `SELECT 1` startup check via asyncpg
- [x] Redis `PING` startup check via redis-py async
- [x] FastAPI lifespan composes all four: settings → check_postgres → check_redis → nats.connect → spawn heartbeat task; reverse on shutdown
- [x] Multi-stage Dockerfile (builder = ghcr.io/astral-sh/uv:python3.12-bookworm-slim, runtime = python:3.12-slim-bookworm), non-root UID 1000, image 290MB on disk / 62MB content
- [x] GHA workflow `build-hello-svc.yml` builds + pushes `:main` and `:sha-<sha>` tags to GHCR on every relevant main-branch change
- [x] K8s manifests at `deploy/hello-svc/` (raw YAML, matches hello-world precedent): namespace + deployment + service. Container `app`, runAsNonRoot, readOnlyRootFilesystem, drop ALL capabilities.
- [x] Argo CD Application at `deploy/applications/hello-svc.yaml` (mirrors hello-world.yaml; 3-line diff: name, path, namespace)
- [x] postgres-oms + redis sealed-secrets created for hello-svc namespace via stdin pipeline (no plaintext on disk)
- [x] Pod 1/1 Running, lifespan completes cleanly, GET /health 200 OK from readiness probes
- [x] **Heartbeat received on `events.heartbeat.hello-svc` from a NATS subscriber in another namespace — full chain proven**
- [x] 22 tests passing (5 BaseEvent + 7 HeartbeatEvent + 1 health + 2 publish_heartbeat + 2 postgres + 2 redis + 3 lifespan)

### ⚪ Task 12 — Document the runbook (NEXT) → v2 §10, §14

- [ ] Document daily check procedure (how to look at the cluster, what "healthy" means)
- [ ] Document incident response (who to alert, how to roll back via Argo)
- [ ] Document common operations (deploy a new service, scale a deployment, restart a pod, rotate a credential, rotate the DigitalOcean token)
- [ ] Phase 1 closes after this lands

---

## ⚪ Phase 2 — Core data layer (3-4 weeks, pending) → v2 §02, §03, §04, §06

> Goal: the data backbone works. No strategies yet, no execution yet. But the system ingests market data, has working event-sourced ledgers, is fully observable.

- [ ] Build `bot-events` package out — define all event schemas: `MarketTick`, `OrderPlaced`, `OrderFilled`, `BankrollChanged`, `PositionOpened`, `PositionClosed`, etc.
- [ ] Build `data-svc` with Kalshi adapter (market data + account data) → v2 §02
- [ ] Build `oms-svc` with event-sourced order log against `oms_db` → v2 §02, §03
- [ ] Build `pms-svc` with event-sourced portfolio log against `pms_db` → v2 §02, §03
- [ ] Deploy all three to `trading-paper` namespace
- [ ] Verify end-to-end: data-svc emits `market.tick` events, visible in Grafana
- [ ] Verify event-sourcing: manually inject a deposit event, verify bankroll projection updates
- [ ] Wire reconciliation jobs to scheduler (Lesson 2)
- [ ] **Execute the cross-DB denial check** carried over from Phase 1 Task 2

---

## ⚪ Phase 3 — First strategy end-to-end (2-3 weeks, pending) → v2 §02, §11 P3

- [ ] Add Anthropic adapter to `data-svc` (AI edge detection)
- [ ] Build `risk-svc` with the gate stack from the existing bot
- [ ] Build `strategy-timely` as the first strategy service
- [ ] Build `ems-svc` in paper mode (simulated fills)
- [ ] Run end-to-end: market arrives → TIMELY proposes → risk approves → OMS records → EMS simulates fill → PMS records bet
- [ ] Watch in Grafana Tempo: see the full distributed trace of one bet

---

## ⚪ Phase 4 — Go live with TIMELY only (2-3 weeks, pending) → v2 §10, §11 P4

- [ ] Build `ems-svc` in live mode (real Kalshi orders)
- [ ] Build `telegram-svc` with basic alerting
- [ ] Set up reconciliation jobs in OMS and PMS
- [ ] Deploy all services to `trading-prod` namespace
- [ ] Run with tiny bankroll ($50-100) for 2-3 weeks
- [ ] Compare results to paper running same strategy
- [ ] Monitor reconciliation alerts daily; address any drift immediately
- [ ] **Old bot officially retired**

---

## ⚪ Phase 5 — Port remaining strategies (3-5 weeks, pending) → v2 §11 P5

- [ ] `strategy-midsel` — the exit strategy
- [ ] `strategy-arb` — cross-platform arb (requires Polymarket adapter in data-svc first)
- [ ] Add Polymarket adapter to data-svc
- [ ] Add `reporting-svc` with daily/weekly reports
- [ ] Add prompt-fragment strategies (FADHYPE, NICHDOM) to AI edge detector
- [ ] Each strategy goes paper → prod through the standard flow

---

## ⚪ Phase 6 — Hardening + MCP integration (3-4 weeks, pending) → v2 §13, §14

- [ ] Build `mcp-svc` with read tools
- [ ] Add simulate tools to MCP
- [ ] Add write tools (pause, resume) with auth
- [ ] Stress-test failure scenarios: kill ems-svc during a fill, kill the database, kill NATS
- [ ] Verify system recovers correctly in each case
- [ ] Write runbooks for each known failure mode
- [ ] Set up alerting rules in Prometheus alertmanager

---

## ⚪ Phase 7 — Research & growth (ongoing, no end date) → v2 §11 P7

- [ ] Move shadow R&D content into experimental strategy services in paper
- [ ] Begin Bayesian-Kelly sizing experiment (paper first, then prod if it outperforms)
- [ ] Add new data sources as MCPs or direct adapters
- [ ] Add new strategies as new services

---

## 🚧 Carry items (cross-cutting, don't lose track)

| Item | Why it matters | When to address |
|---|---|---|
| **Postgres oms_user + Redis default passwords leaked May 9 in chat** | Both creds appeared in plaintext in chat transcript via `kubectl get secret -o jsonpath='{.data}'`. VPC-only access mitigates external risk. | Rotate when convenient (use `kubectl get secret X -o go-template='{{range $k,$v := .data}}{{$k}}{{"\n"}}{{end}}'` next time to print only keys) |
| **Local gh token missing read:packages / write:packages scopes** | Can't list GHCR packages from CLI. Browser works. CI uses GITHUB_TOKEN, unaffected. | Optional, fix if doing manual GHCR debugging |
| **`/health` is dumb liveness only** | Currently returns `{ok: true}` regardless of dependency state. Real readiness should probe Postgres/Redis/NATS. | Split into `/health` (process up) + `/ready` (deps healthy) before first real strategy ships |
| **`nc.close()` vs `nc.drain()` in lifespan teardown** | Fine for fire-and-forget heartbeats. Drain matters when there are pending replies that need to flush. | Revisit when first request/reply consumer ships |
| **`imagePullPolicy: Always` + mutable `:main` tag** | Argo CD sees no diff when image content changes. No version pinning, no rollback by tag. Argo Image Updater would automate. | Switch to per-SHA pinning before first real strategy ships |
| **Container name `app` (not service name)** | Avoids `kubectl logs hello-svc -c hello-svc` collision. | Keep as convention for all future services |
| **GHA actions on Node.js 20** | GitHub forces Node.js 24 default June 2 2026, removes Node.js 20 Sep 16 2026. | Bump action pins (checkout, setup-buildx, login, build-push) when v5/v7+ Node-24-compatible versions ship |
| **NATS Argo Application shows OutOfSync** | Cosmetic — pods healthy, traffic serving. Helm chart writes some immutable fields Argo doesn't recognize. | Investigate when convenient |
| **`docker manifest inspect` from Mac returns 401 even though DOKS pulls fine** | After GHCR public flip, Filippo's local curl still got 401, but DOKS pulled successfully. Possibly GHCR routing/cache or undocumented anonymous-pull semantics. | Investigate once if the public-vs-private question recurs |
| **Future bot-events consumers each need own paths entry in build workflow** | Phase 2's data-svc / oms-svc / pms-svc each need a `build-<svc>.yml` with `paths: [services/<svc>/**, packages/bot-events/**, ...]`. No automatic "rebuild all consumers". | When building each new service in Phase 2 |
| **doctl 1.158.0 removed `--kubeconfig` flag** | Use `KUBECONFIG=path doctl ...` instead. | Document in Task 12 runbook |
| **Mac onboarding sequence (~45 min)** | brew → kubectl → doctl → gh → uv → OrbStack → kubeseal → kubeconfig save. Peter's Mac required full bootstrap session 5. | Document in Task 12 runbook |
| **DO droplet limit at 3 (currently capped)** | Cluster is 3 nodes, at the cap. Can't add a 4th node or any standalone droplet without a limit increase request (~1-3hr). | Request bump before scaling cluster |
| **DO account status "warning"** | `doctl account get` shows Status: warning. Reason unknown. Not blocking current work but DO can suspend warning accounts. | Investigate in DO console next session |
| **pytest basename collisions (e.g. `test_heartbeat.py` in two packages)** | Solved by adding `addopts = "--import-mode=importlib"` to root `pyproject.toml`. Future packages can name files however. | Pattern locked in, no further action |
| Cross-DB denial check (oms_user → pms_db) | Verifies Postgres role isolation | Phase 2 (when wiring service permissions) |
| DigitalOcean API token expires ~July 27, 2026 | If expired, doctl stops working | Set calendar reminder for ~July 20, 2026 |

---

## 💡 Working agreements (read these every session)

1. **Filippo says when to stop.** Claude does not ask "should we stop?" — annoying.
2. **Claude pushes back on shortcuts.** If a proposal violates one of the 10 lessons, name the lesson, suggest the alternative, ask whether to proceed. Don't refuse outright.
3. **Decisions inline; documents follow.** Move forward fast, document afterward in handoff doc.
4. **Verify before commit.** Claude Code may ask for review before commit/push.
5. **Never paste passwords/tokens in chat.** They go in Filippo's password manager.
6. **One visible win per week minimum.** If a week passes with no commit landed, something is wrong.
7. **The 10 lessons are binding.** Not suggestions.
8. **Migration goal: same behavior, new architecture.** Don't fix bugs while porting (architecture v2 Section 11). Behavioral changes come AFTER migration is done.

---

## 📊 By the numbers (current)

- **Commits on main:** 28
- **Latest commit:** `006929b` feat(secrets): seal postgres-oms and redis for hello-svc namespace
- **Current phase:** Phase 1 (infrastructure foundation)
- **Phase 1 progress:** **11 / 12 tasks complete**
- **Overall progress:** 0 of 7 active phases complete (Phase 1 nearly done)
- **Cloud cost:** ~$130 / month (target: <$150)
- **Quality gates:** 3 / 3 passing (install, lint, test)
- **Tests:** 22 passing
- **Services running:** 1 application service (hello-svc) + cluster infrastructure (Argo CD, sealed-secrets, NATS, kps, Loki, Tempo)
- **Last session:** May 9, 2026 (~7h, hello-svc end-to-end shipped, 10 commits)
