# Midas — Living TODO

> **Updated:** May 4, 2026 (mid-session 2, post-Task 5)
> **Format:** Living checklist. Updated at end of every session.
> **Aligned with:**
> - The big picture → `Bot_Architecture_v2_Professional_Grade_April26_2026.html` Section 11 (8-phase migration roadmap)
> - The granular Phase 1 work → `docs/PHASE_1_PLAN.md`
> **Pair this with:** `docs/PROJECT_HANDOFF.html` (current state) and `docs/SESSION_HISTORY.md` (chronological session log)

---

## 🎯 Right now — Next session opens here

- [ ] **Phase 1 Task 6** — Install Argo CD into `midas-prod`, point it at `deploy/` in this repo (per Task 5 decision), verify the dashboard is reachable via port-forward, configure RBAC.

---

## 📊 Phase status at a glance

| Phase | Description | Duration estimate | Status |
|---|---|---|---|
| **Phase 0** | Keep the lights on (old bot paused) | ongoing | ✅ Active |
| **Phase 1** | Infrastructure foundation | 2-4 weeks | 🟡 In progress (5/12 tasks) |
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

- [x] Create monorepo at `/Users/filippominella/midas/`
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

## 🟡 Phase 1 — Infrastructure foundation (5/12 tasks complete)

> Goal: a functional empty cluster with all infrastructure running. No trading services yet. You can `kubectl apply` a hello-world service and see it appear in Grafana with logs and metrics.

### ✅ Task 1 — Kubernetes cluster (DONE)

- [x] Create DigitalOcean account (`bakerlunch@gmail.com`, project `midas`)
- [x] Set $150/month billing alert
- [x] Enable 2FA on DigitalOcean account
- [x] Provision `midas-prod`: 3 nodes, Premium Intel, $24/node, London, K8s 1.35.1-do.3
- [x] Skip HA control plane (saves $40/mo)
- [x] Install kubectl, doctl, uv on Filippo's MacBook
- [x] Authenticate doctl with API token
- [x] Save kubeconfig at `~/.kube/config-midas`
- [x] Verify `kubectl get nodes` returns 3 Ready nodes
- [x] Document doctl 1.155+ kubeconfig flag change

### ✅ Task 2 — Managed PostgreSQL (DONE)

- [x] Provision `midas-postgres`: PG18, Regular SSD, $24/mo, 30 GiB
- [x] Skip standby node (single primary)
- [x] Enable storage autoscaling (90% threshold, +10 GiB increments)
- [x] Lock down network access — only `midas-prod` allowed
- [x] Create three logical databases: `oms_db`, `pms_db`, `reporting_db`
- [x] Create three users: `oms_user`, `pms_user`, `reporting_user`
- [x] Save credentials in password manager
- [x] Proof-of-life: pod connects to Postgres over VPC, runs `SELECT 1` ✅
- [ ] Cross-DB denial check (oms_user → pms_db should fail) — **deferred to Phase 2** when service permissions are wired

### ✅ Task 3 — Managed Redis (DONE)

- [x] Provision `midas-redis`: Valkey 8, Basic Regular SSD, 1GB / 1vCPU / 10 GiB, $15/mo, London
- [x] Lock down network access — only `midas-prod` allowed
- [x] Save credentials in password manager (password reset twice after accidental chat leaks)
- [x] Proof-of-life: ephemeral pod inside `midas-prod` ran `redis-cli ... ping` → `PONG`

### ✅ Task 4 — GitHub Actions CI (DONE)

- [x] Create `.github/workflows/ci.yml` running `make install`, `make lint`, `make test`
- [x] Verified green on PR #1 before squash-merging to main
- [x] `uv.lock` now tracked in git (was in stock `.gitignore` — removed for reproducible CI builds)
- [ ] Add branch protection on `main` requiring CI to pass before merge — **deferred**: requires GitHub Team plan ($16/mo) for private repos. Staying on free plan; relying on team discipline. Re-evaluate if team grows or if broken code lands on main.

### ✅ Task 5 — Decide on midas-deploy repo (DONE)

- [x] Decision recorded: **manifests in-tree at `deploy/`**, no separate `midas-deploy` repo. Reasoning captured in `docs/PHASE_1_PLAN.md` Task 5.
- [x] `deploy/README.md` placeholder added explaining what lives there
- [x] Re-evaluate trigger: team growth, ops/eng permission boundary, or CI-on-every-infra-commit cost becoming annoying

### ⚪ Task 6 — Argo CD (GitOps) (next up)

- [ ] Install Argo CD into `midas-prod`
- [ ] Point at `deploy/` in `bakerlunch-ai/midas` (per Task 5 decision)
- [ ] Verify dashboard reachable (port-forward only — no public IP yet)
- [ ] Configure RBAC

### ⚪ Task 7 — Sealed-secrets

- [ ] Install sealed-secrets controller into `midas-prod`
- [ ] Save the public/private key pair securely
- [ ] Verify `kubeseal` CLI works from laptop

### ⚪ Task 8 — Move credentials into sealed-secrets

- [ ] Create sealed secrets for: postgres credentials (per service), DigitalOcean token, future Kalshi/Telegram tokens
- [ ] Commit sealed secrets to deploy repo (encrypted, safe to commit)
- [ ] Verify pods can read decrypted values via `envFrom`

### ⚪ Task 9 — NATS JetStream

- [ ] Deploy NATS JetStream cluster (3 replicas) to `midas-prod`
- [ ] Configure persistent storage
- [ ] Verify cross-replica replication
- [ ] Test publish/subscribe from a client pod

### ⚪ Task 10 — LGTM observability stack

- [ ] Deploy Prometheus (metrics)
- [ ] Deploy Loki (logs)
- [ ] Deploy Tempo (traces)
- [ ] Deploy Grafana with default datasource configs
- [ ] Configure ingress / port-forward access
- [ ] Verify cluster metrics appear in Grafana

### ⚪ Task 11 — Hello-world end-to-end deploy

- [ ] Build trivial Python service ("hello-svc") exposing `/health`
- [ ] Containerize, push to DigitalOcean container registry
- [ ] Deploy via Argo CD
- [ ] Verify it shows up in Grafana logs and metrics

### ⚪ Task 12 — Document the runbook

- [ ] Document daily check procedure
- [ ] Document incident response (who to alert, how to roll back)
- [ ] Document common operations (deploy, scale, restart, rotate token)

### ⚪ Phase 1 not in original task list (added during architecture v2 review)

- [ ] Set up CloudFlare tunnel (referenced in architecture v2 Section 11 Phase 1)
- [ ] Create `trading-paper` namespace; `trading-prod` namespace exists but empty

---

## ⚪ Phase 2 — Core data layer (3-4 weeks)

> Goal: the data backbone works. No strategies yet, no execution yet. But the system ingests market data, has working event-sourced ledgers, is fully observable.

- [ ] Build `bot-events` package out — define all event schemas: `MarketTick`, `OrderPlaced`, `OrderFilled`, `BankrollChanged`, `PositionOpened`, `PositionClosed`, etc.
- [ ] Build `data-svc` with Kalshi adapter (market data + account data)
- [ ] Build `oms-svc` with event-sourced order log against `oms_db`
- [ ] Build `pms-svc` with event-sourced portfolio log against `pms_db`
- [ ] Deploy all three to `trading-paper` namespace
- [ ] Verify end-to-end: data-svc emits `market.tick` events, visible in Grafana
- [ ] Verify event-sourcing: manually inject a deposit event, verify bankroll projection updates
- [ ] Wire reconciliation jobs to scheduler (Lesson 2)
- [ ] **Execute the cross-DB denial check** carried over from Phase 1 Task 2

---

## ⚪ Phase 3 — First strategy end-to-end (2-3 weeks)

> Goal: the first strategy runs end-to-end in paper. This validates the entire architecture with a real workload before any real money is involved.

- [ ] Add Anthropic adapter to `data-svc` (AI edge detection)
- [ ] Build `risk-svc` with the gate stack from the existing bot
- [ ] Build `strategy-timely` as the first strategy service
- [ ] Build `ems-svc` in paper mode (simulated fills)
- [ ] Run end-to-end: market arrives → TIMELY proposes → risk approves → OMS records → EMS simulates fill → PMS records bet
- [ ] Watch in Grafana Tempo: see the full distributed trace of one bet

---

## ⚪ Phase 4 — Go live with TIMELY only (2-3 weeks)

> Goal: the new architecture is live, trading real money, with TIMELY only. The old bot can be retired.

- [ ] Build `ems-svc` in live mode (real Kalshi orders)
- [ ] Build `telegram-svc` with basic alerting
- [ ] Set up reconciliation jobs in OMS and PMS
- [ ] Deploy all services to `trading-prod` namespace
- [ ] Run with tiny bankroll ($50-100) for 2-3 weeks
- [ ] Compare results to paper running same strategy
- [ ] Monitor reconciliation alerts daily; address any drift immediately
- [ ] **Old bot officially retired**

---

## ⚪ Phase 5 — Port remaining strategies (3-5 weeks)

> Goal: all of the old bot's actual functionality now in the new architecture, plus better observability, plus better reliability.

- [ ] `strategy-midsel` — the exit strategy
- [ ] `strategy-arb` — cross-platform arb (requires Polymarket adapter in data-svc first)
- [ ] Add Polymarket adapter to data-svc
- [ ] Add `reporting-svc` with daily/weekly reports
- [ ] Add prompt-fragment strategies (FADHYPE, NICHDOM) to AI edge detector
- [ ] Each strategy goes paper → prod through the standard flow

---

## ⚪ Phase 6 — Hardening + MCP integration (3-4 weeks)

> Goal: the system is genuinely production-grade. MCP exposes the bot to Claude as a first-class system. Operational practices (runbooks, alerts) in place.

- [ ] Build `mcp-svc` with read tools
- [ ] Add simulate tools to MCP
- [ ] Add write tools (pause, resume) with auth
- [ ] Stress-test failure scenarios: kill ems-svc during a fill, kill the database, kill NATS
- [ ] Verify system recovers correctly in each case
- [ ] Write runbooks for each known failure mode
- [ ] Set up alerting rules in Prometheus alertmanager

---

## ⚪ Phase 7 — Research & growth (ongoing, no end date)

> This phase has no end date — it's how the bot grows.

- [ ] Move shadow R&D content into experimental strategy services in paper
- [ ] Begin Bayesian-Kelly sizing experiment (paper first, then prod if it outperforms)
- [ ] Add new data sources as MCPs or direct adapters
- [ ] Add new strategies as new services

---

## 🚧 Carry items (cross-cutting, don't lose track)

| Item | Why it matters | When to address |
|---|---|---|
| DigitalOcean API token expires ~July 27, 2026 | If expired, doctl stops working | Set calendar reminder for ~July 20, 2026 |
| Cross-DB denial check (oms_user → pms_db) | Verifies Postgres role isolation | Phase 2 (when wiring service permissions) |
| Connection strings only in password manager | Risk of human error, hard to share | Phase 1 Task 8 (sealed-secrets) |
| ~~Decision: midas-deploy repo or in-tree manifests~~ | ~~Affects all of Tasks 5-11~~ | **Resolved 2026-05-04:** in-tree at `deploy/` |
| Decision: Helm vs plain Kustomize | Affects manifest authoring style | Phase 1 Task 9-11 |
| `docs/ARCHITECTURE.md` is a placeholder | Will fill as services come online | Phase 2+ (per service) |
| CloudFlare tunnel setup | Referenced in arch v2 Phase 1 but not yet in PHASE_1_PLAN | Add to PHASE_1_PLAN as Task 13 |
| `trading-paper` and `trading-prod` namespaces | Architecture v2 assumes these exist by end of Phase 1 | Add to PHASE_1_PLAN as Task 14 |

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

- **Commits on main:** 12 (will be 13 after this push lands)
- **Current phase:** Phase 1 (infrastructure foundation)
- **Phase 1 progress:** 5 / 12 tasks complete
- **Overall progress:** 0 of 7 active phases complete
- **Cloud cost:** $117.45 / month (target: <$150)
- **Quality gates:** 4 / 4 passing (install, lint, test, CI on every push)
- **Tests:** 5 passing
- **Services running:** 0 (Phase 2 work)
- **Last session:** April 29, 2026 (~3h, 2 tasks shipped); session 2 in progress (2026-05-04, Tasks 3+4+5 shipped)
