# Midas — Living TODO

> **Updated:** May 4, 2026 (end of session 2)
> **Format:** Living checklist. Updated at end of every session.
> **Aligned with:**
> - The big picture → `Bot_Architecture_v2_Professional_Grade_April26_2026.html` (v2 architecture, all sections)
> - The narrative arc → `docs/JOURNEY.md` (why each phase exists, what it enables)
> - The granular Phase 1 work → `docs/PHASE_1_PLAN.md`
>
> **Pair this with:** `docs/PROJECT_HANDOFF.html` (current state) and `docs/SESSION_HISTORY.md` (chronological session log)

---

## 🎯 Right now — Next session opens here

- [ ] **Phase 1 Task 7** — Install sealed-secrets controller into `midas-prod`, save the public/private keypair securely, install `kubeseal` CLI on Filippo's laptop, verify a test secret can be sealed → committed to `deploy/` → automatically decrypted by the cluster after Argo CD syncs it. → v2 §7

---

## 📊 Phase status at a glance

| Phase | Description | v2 ref | Duration estimate | Status |
|---|---|---|---|---|
| **Phase 0** | Keep the lights on (old bot paused) | §11 | ongoing | ✅ Active |
| **Phase 1** | Infrastructure foundation | §6, §7, §8, §11 | 2-4 weeks | 🟡 In progress (6/12 tasks) |
| **Phase 2** | Core data layer (data, oms, pms services) | §5, §9, §10, §11 | 3-4 weeks | ⚪ Pending |
| **Phase 3** | First strategy end-to-end (paper) | §11, §12 | 2-3 weeks | ⚪ Pending |
| **Phase 4** | Go live with TIMELY only | §11 | 2-3 weeks | ⚪ Pending |
| **Phase 5** | Port remaining strategies | §11 | 3-5 weeks | ⚪ Pending |
| **Phase 6** | Hardening + MCP integration | §11, §13 | 3-4 weeks | ⚪ Pending |
| **Phase 7** | Research & growth | §11, §14 | ongoing | ⚪ Pending |

**Total realistic timeline: 5-6 months calendar time, evenings/weekends.**

For why each phase exists and what it enables, see **`docs/JOURNEY.md`**.

---

## ✅ Phase 0 — Keep the lights on (ongoing)

- [x] Old Kalshi bot paused per audit synthesis
- [ ] If trading resumes during migration, do it on the OLD bot with audit fixes applied (specifically the bankroll accounting fix), NOT the half-built new system

---

## ✅ Repo bootstrap (pre-Phase 1, completed in session 1)

- [x] Create monorepo at `/Users/filippominella/Desktop/midas/`
- [x] Set up uv workspace with `packages/bot-events/`
- [x] Build `BaseEvent` Pydantic v2 class with `ClassVar` + `__init_subclass__` enforcement → closes Lesson #3
- [x] Write 5 unit tests for `BaseEvent` (all passing)
- [x] Configure ruff, pytest, Makefile (install/lint/format/test)
- [x] All quality gates green
- [x] Push to `github.com/bakerlunch-ai/midas` (private)
- [x] Authenticate `gh`, `doctl`; install kubectl
- [x] Write `docs/LESSONS_FROM_OLD_BOT.md` (10 binding constraints)
- [x] Write `docs/PHASE_1_PLAN.md` (12-task plan)
- [x] Save Claude Code feedback memory

---

## 🟡 Phase 1 — Infrastructure foundation (6/12 tasks complete)

> Goal: a functional empty cluster with all infrastructure running. No trading services yet. You can `kubectl apply` a hello-world service and see it appear in Grafana with logs and metrics.
>
> **v2 reference: §6 (data stores), §7 (operational stack), §8 (observability), §11 (Phase 1 description)**

### ✅ Task 1 — Kubernetes cluster (DONE) → v2 §7

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

### ✅ Task 2 — Managed PostgreSQL (DONE) → v2 §6

- [x] Provision `midas-postgres`: PG18, Regular SSD, $24/mo, 30 GiB
- [x] Skip standby node (single primary)
- [x] Enable storage autoscaling (90% threshold, +10 GiB increments)
- [x] Lock down network access — only `midas-prod` allowed
- [x] Create three logical databases: `oms_db`, `pms_db`, `reporting_db`
- [x] Create three users: `oms_user`, `pms_user`, `reporting_user`
- [x] Save credentials in password manager
- [x] Proof-of-life: pod connects to Postgres over VPC, runs `SELECT 1` ✅
- [ ] Cross-DB denial check (oms_user → pms_db should fail) — **deferred to Phase 2** when service permissions are wired

### ✅ Task 3 — Managed Redis (DONE) → v2 §6

- [x] Provision `midas-redis`: Valkey 8, Basic Regular SSD, 1GB / 1vCPU / 10 GiB, $15/mo, London
- [x] Lock down network access — only `midas-prod` allowed
- [x] Save credentials in password manager (password reset twice after accidental chat leaks)
- [x] Proof-of-life: ephemeral pod inside `midas-prod` ran `redis-cli ... ping` → `PONG`

### ✅ Task 4 — GitHub Actions CI (DONE) → closes Lesson #10

- [x] Create `.github/workflows/ci.yml` running `make install`, `make lint`, `make test`
- [x] Verified green on PR #1 before squash-merging to main
- [x] `uv.lock` now tracked in git (was in stock `.gitignore` — removed for reproducible CI builds)
- [ ] Add branch protection on `main` requiring CI to pass before merge — **deferred**: requires GitHub Team plan ($16/mo) for private repos. Staying on free plan; relying on team discipline. Re-evaluate if team grows or if broken code lands on main.

### ✅ Task 5 — Decide on midas-deploy repo (DONE)

- [x] Decision recorded: **manifests in-tree at `deploy/`**, no separate `midas-deploy` repo. Reasoning captured in `docs/PHASE_1_PLAN.md` Task 5.
- [x] `deploy/README.md` placeholder added explaining what lives there
- [x] Re-evaluate trigger: team growth, ops/eng permission boundary, or CI-on-every-infra-commit cost becoming annoying

### ✅ Task 6 — Argo CD (GitOps) (DONE) → v2 §7

- [x] Install Argo CD v3.3.9 into `midas-prod` (7/7 pods Ready in `argocd` namespace)
- [x] Install `argocd` CLI on Filippo's laptop via Homebrew (also v3.3.9, matches server)
- [x] Rotate admin password via CLI (`argocd account update-password`); verified by logout + re-login. Final password matches PM. **Lesson: rotate via CLI, not UI.**
- [x] Generate fine-grained GitHub PAT (`midas-argocd-readonly`, Contents: Read-only on `bakerlunch-ai/midas`, 90-day expiry); save to PM
- [x] Connect Argo CD to repo via `argocd repo add` using the PAT
- [x] Hello-world smoke test: created `deploy/hello-world/{namespace,deployment,service}.yaml` + `deploy/applications/hello-world.yaml` Argo CD Application; nginx pod synced & healthy ✅
- [x] Dashboard reachable via `kubectl port-forward` (no public IP yet — TLS to be addressed later)
- [x] RBAC: default Argo CD RBAC config kept; revisit when more than one human operator is added

### ⚪ Task 7 — Sealed-secrets (next up) → v2 §7

- [ ] Install sealed-secrets controller into `midas-prod` (Helm or upstream manifest)
- [ ] Save the controller's public/private keypair securely (this is the master key — losing it means losing all sealed secrets)
- [ ] Verify `kubeseal` CLI works from laptop
- [ ] Test: seal a dummy secret, commit to `deploy/`, watch Argo CD apply it, confirm it's decrypted in-cluster

### ⚪ Task 8 — Move credentials into sealed-secrets

- [ ] Create sealed secrets for: postgres credentials (per service), Redis credentials, future Kalshi/Telegram tokens
- [ ] Commit sealed secrets to `deploy/secrets/` (encrypted, safe to commit)
- [ ] Verify pods can read decrypted values via `envFrom: secretRef`
- [ ] Argo CD admin password should also be backed up here (currently PM-only)

### ⚪ Task 9 — NATS JetStream → v2 §7

- [ ] Deploy NATS JetStream cluster (3 replicas) to `midas-prod`
- [ ] Configure persistent storage
- [ ] Verify cross-replica replication
- [ ] Test publish/subscribe from a client pod

### ⚪ Task 10 — LGTM observability stack → v2 §8

- [ ] Deploy Prometheus (metrics)
- [ ] Deploy Loki (logs)
- [ ] Deploy Tempo (traces)
- [ ] Deploy Grafana with default datasource configs
- [ ] Configure ingress / port-forward access
- [ ] Verify cluster metrics appear in Grafana

### ⚪ Task 11 — Hello-world end-to-end deploy

- [x] Build trivial nginx service via Argo CD GitOps (done as part of Task 6 smoke test)
- [ ] Build trivial Python service ("hello-svc") exposing `/health` (real proof-of-life closer to actual Phase 2 work)
- [ ] Containerize, push to DigitalOcean container registry
- [ ] Deploy via Argo CD
- [ ] Verify it shows up in Grafana logs and metrics (after Task 10)
- *(Consider folding into Task 6 since the GitOps shape is already proven; Task 11's distinct value is observability integration — defer until after Task 10.)*

### ⚪ Task 12 — Document the runbook

- [ ] Document daily check procedure
- [ ] Document incident response (who to alert, how to roll back)
- [ ] Document common operations (deploy, scale, restart, rotate token)

### ⚪ Phase 1 not in original task list (added during architecture v2 review)

- [ ] Set up CloudFlare tunnel (referenced in v2 §11 Phase 1)
- [ ] Create `trading-paper` namespace; `trading-prod` namespace exists but empty

---

## ⚪ Phase 2 — Core data layer (3-4 weeks)

> Goal: the data backbone works. No strategies yet, no execution yet. But the system ingests market data, has working event-sourced ledgers, is fully observable.
>
> **v2 reference: §5 (event sourcing), §9 (data-svc), §10 (OMS/PMS), §11 (Phase 2)**

- [ ] Build `bot-events` package out — define all event schemas: `MarketTick`, `OrderPlaced`, `OrderFilled`, `BankrollChanged`, `PositionOpened`, `PositionClosed`, etc. → v2 §5
- [ ] Build `data-svc` with Kalshi adapter (market data + account data) → v2 §9
- [ ] Build `oms-svc` with event-sourced order log against `oms_db` → v2 §10
- [ ] Build `pms-svc` with event-sourced portfolio log against `pms_db` → v2 §10
- [ ] Deploy all three to `trading-paper` namespace
- [ ] Verify end-to-end: data-svc emits `market.tick` events, visible in Grafana
- [ ] Verify event-sourcing: manually inject a deposit event, verify bankroll projection updates → closes Lesson #1
- [ ] Wire reconciliation jobs to scheduler → closes Lesson #2
- [ ] **Execute the cross-DB denial check** carried over from Phase 1 Task 2

---

## ⚪ Phase 3 — First strategy end-to-end (2-3 weeks)

> Goal: the first strategy runs end-to-end in paper. This validates the entire architecture with a real workload before any real money is involved.
>
> **v2 reference: §11 (Phase 3), §12 (strategy service pattern)**

- [ ] Add Anthropic adapter to `data-svc` (AI edge detection) → v2 §9
- [ ] Build `risk-svc` with the gate stack from the existing bot → closes Lesson #5 (one canonical risk implementation)
- [ ] Build `strategy-timely` as the first strategy service → v2 §12
- [ ] Build `ems-svc` in paper mode (simulated fills)
- [ ] Run end-to-end: market arrives → TIMELY proposes → risk approves → OMS records → EMS simulates fill → PMS records bet
- [ ] Watch in Grafana Tempo: see the full distributed trace of one bet

---

## ⚪ Phase 4 — Go live with TIMELY only (2-3 weeks)

> Goal: the new architecture is live, trading real money, with TIMELY only. Every other strategy still on the legacy bot or off entirely.
>
> **v2 reference: §11 (Phase 4)**

- [ ] Switch `ems-svc` to live mode against Kalshi
- [ ] Start with $50 bankroll cap as a circuit breaker
- [ ] Run for 2 weeks side-by-side with legacy paused
- [ ] Compare per-bet decisions to what the legacy bot would have done (if any of legacy is still live)
- [ ] Increase bankroll cap if metrics look healthy

---

## ⚪ Phase 5 — Port remaining strategies (3-5 weeks)

> One strategy at a time, through paper, then live. NOT a parallel mass port.
>
> **v2 reference: §11 (Phase 5)**

- [ ] Port MIDSEL (exit logic) to `strategy-midsel`
- [ ] Port arb scanner to `strategy-arb`
- [ ] Decide what to do with FADHYPE / NICHDOM (prompt fragments — possibly fold into `data-svc` AI prompts rather than separate services)
- [ ] Permanently delete XMKTARB and LNGSHOT (dead code in legacy bot, never resurrect per audit) → closes Lesson #4
- [ ] After all strategies ported: officially shut down legacy bot

---

## ⚪ Phase 6 — Hardening + MCP integration (3-4 weeks)

> MCP exposes the bot to Claude as a first-class system. Operational practices (runbooks, alerts) in place.
>
> **v2 reference: §11 (Phase 6), §13 (MCP design)**

- [ ] Build `mcp-svc` with read tools → v2 §13
- [ ] Add simulate tools to MCP
- [ ] Add write tools (pause, resume) with auth
- [ ] Stress-test failure scenarios: kill ems-svc during a fill, kill the database, kill NATS
- [ ] Verify system recovers correctly in each case
- [ ] Write runbooks for each known failure mode
- [ ] Set up alerting rules in Prometheus alertmanager

---

## ⚪ Phase 7 — Research & growth (ongoing, no end date)

> This phase has no end date — it's how the bot grows.
>
> **v2 reference: §11 (Phase 7), §14 (research patterns)**

- [ ] Move shadow R&D content into experimental strategy services in paper
- [ ] Begin Bayesian-Kelly sizing experiment (paper first, then prod if it outperforms)
- [ ] Add new data sources as MCPs or direct adapters
- [ ] Add new strategies as new services

---

## 🛠️ Session-close workflow improvements (added 2026-05-04)

> Tonight surfaced that the session-close protocol works but takes more friction than it should, and the session reports were not connecting strongly enough to the v2 architecture. These items improve both.

### Trigger phrases & automation

- [ ] **Add more trigger phrases to project instructions.** Beyond "session close" / "wrap up" / "good night", add: "save what we did", "lock it in", "back this up", "stop here", "wrap protocol", "save this somewhere", "i need a backup". Anything that sounds like end-of-session should auto-trigger the four-document update.
- [ ] **Add safety net rule.** If a chat reaches ~2 hours of activity, Claude proactively offers session close instead of waiting for Filippo to remember. Phrasing: "We've been at this for 2 hours — want me to wrap and save before we keep going?"
- [ ] **Write `docs/SESSION_CLOSE_PROTOCOL.md`** so Claude Code can do basic doc updates from git history alone, without chat-side input. Use this for "routine" sessions where nothing dramatic happened. The chat-side full version (what we did 2026-05-04) stays for big sessions with real lessons worth preserving.
- [ ] **Decision criteria** in SESSION_CLOSE_PROTOCOL.md: when to use chat-side full version vs Claude-Code lite version. Probably: lite for "shipped task X cleanly, nothing surprising"; full for "shipped task X but with notable issues / decisions / new lessons".

### Why-this-matters template enforcement

- [ ] **Every future session report** must include a "Why this matters" section connecting the session's work to the v2 architecture and the journey arc. 1-3 paragraphs. Reference specific v2 §X sections. Reference the journey doc.
- [ ] **The session-close template** in SESSION_CLOSE_PROTOCOL.md must enforce this — Claude Code or Claude chat must always fill out this section before considering the session closed.

### JOURNEY.md update cadence

- [ ] **Update `docs/JOURNEY.md` whenever:** (a) a phase completes, (b) understanding of why a phase exists changes, (c) a major architectural decision is made that the v2 doc doesn't cover. Otherwise, leave alone.
- [ ] **Read `docs/JOURNEY.md` at the start of every session** as part of the warm-up. It's listed in the PROJECT_HANDOFF "Open the next session by..." checklist.
- [ ] **If JOURNEY.md gets stale** (multiple sessions go by without updating it when a phase changes status), that's a signal the project has lost connection to its own purpose. Reconnect before continuing.

### Backfilling

- [x] Backfilled "Why this matters" into `SESSION_REPORT_2026-04-29.html` (done 2026-05-04)
- [x] Added "Why this matters" to `SESSION_REPORT_2026-05-04.html` (done 2026-05-04)
- [x] Wrote initial `docs/JOURNEY.md` (done 2026-05-04)
- [x] Cross-referenced v2 §X throughout PROJECT_HANDOFF.html and TODO.md (done 2026-05-04)

---

## 🚧 Carry items (cross-cutting, don't lose track)

| Item | Why it matters | When to address |
|---|---|---|
| DigitalOcean API token expires ~July 27, 2026 | If expired, doctl stops working | Set calendar reminder for ~July 20, 2026 |
| GitHub PAT (`midas-argocd-readonly`) expires ~August 2, 2026 | If expired, Argo CD stops syncing the repo | Set calendar reminder for ~July 25, 2026 |
| Cross-DB denial check (oms_user → pms_db) | Verifies Postgres role isolation | Phase 2 (when wiring service permissions) |
| Connection strings only in password manager | Risk of human error, hard to share | Phase 1 Task 8 (sealed-secrets) |
| Argo CD admin password only in password manager | Should be backed up via sealed-secrets | Phase 1 Task 8 |
| ~~Decision: midas-deploy repo or in-tree manifests~~ | ~~Affects all of Tasks 5-11~~ | **Resolved 2026-05-04:** in-tree at `deploy/` |
| Decision: Helm vs plain Kustomize | Affects manifest authoring style | Phase 1 Task 9-11 |
| `docs/ARCHITECTURE.md` is a placeholder | Will fill as services come online | Phase 2+ (per service) |
| CloudFlare tunnel setup | Referenced in v2 §11 Phase 1 but not yet in PHASE_1_PLAN | Add to PHASE_1_PLAN as Task 13 |
| `trading-paper` and `trading-prod` namespaces | v2 architecture assumes these exist by end of Phase 1 | Add to PHASE_1_PLAN as Task 14 |
| PHASE_1_PLAN Tasks 6–11 reference "midas-deploy repo" | Wording is now wrong (in-tree decided) | Rewrite each task's prose in its own session before that task starts |
| `hello-world` Argo CD Application | Should we remove it or keep as permanent smoke test? | Decide before Task 9 (NATS) lands so the "first non-test app" is clearly distinguishable |
| Branch protection on `main` | Requires paid GitHub Team plan ($16/mo) | Deferred until team grows or broken code lands on main |
| Session-close protocol formalization | Currently lives in project instructions only; should also exist in repo | When SESSION_CLOSE_PROTOCOL.md is written (see "Session-close workflow" section above) |

---

## 💡 Working agreements (read these every session)

1. **Filippo says when to stop.** Claude does not ask "should we stop?" — annoying.
2. **Claude pushes back on shortcuts.** If a proposal violates one of the 10 lessons, name the lesson, suggest the alternative, ask whether to proceed. Don't refuse outright.
3. **Decisions inline; documents follow.** Move forward fast, document afterward in handoff doc.
4. **Verify before commit.** Claude Code may ask for review before commit/push.
5. **Never paste passwords/tokens in chat.** They go in Filippo's password manager. (Reinforced session 2 — leaked twice.)
6. **One visible win per week minimum.** If a week passes with no commit landed, something is wrong.
7. **The 10 lessons are binding.** Not suggestions.
8. **Migration goal: same behavior, new architecture.** Don't fix bugs while porting (v2 §11). Behavioral changes come AFTER migration is done.
9. **Rotate credentials via CLI, not UI** (added session 2). UI rotation forms have failure modes — typo in confirm field, PM autosave drift. CLI is reliable.
10. **For interactive prompts, use real Mac Terminal** (added session 2). Claude Code's `!` prefix breaks password prompts because its pseudo-TTY can't disable terminal echo.

---

## 📊 By the numbers (current)

- **Commits on main:** 14 (will be 15 after the session-close commit lands)
- **Current phase:** Phase 1 (infrastructure foundation)
- **Phase 1 progress:** 6 / 12 tasks complete (50%)
- **Overall progress:** 0 of 7 active phases complete
- **Cloud cost:** $117.45 / month (target: <$150)
- **Quality gates:** 5 / 5 passing (install, lint, test, CI on every push, GitOps deploys)
- **Tests:** 5 passing
- **Services running:** 1 (nginx smoke test in `hello-world` namespace) + Argo CD (7 pods in `argocd` namespace)
- **Last session:** May 4, 2026 (~3.5h, Tasks 3+4+5+6 shipped)
- **Sessions to date:** 2
