# Midas — Living TODO

> **Updated:** May 27, 2026 (end of session 8)
> **Format:** Living checklist. Updated at end of every session.
> **Aligned with:** `Bot_Architecture_v2_Professional_Grade_April26_2026.html` §11 (8-phase roadmap) and `docs/PHASE_1_PLAN.md`.
> **Pair this with:** `docs/PROJECT_HANDOFF.html` (current state), `docs/JOURNEY.md` (the arc), `docs/SESSION_HISTORY.md` (audit trail).

---

## 🎯 Right now — Next session opens here

- [ ] **data-svc market selection** → v2 §07. The default `list_markets(status="open", limit=200)` returns only page one — currently a firehose of zero-liquidity KXMVE sports-combo markets. The traded series (KXFED / KXPRES / KXECON) may be absent entirely. **This is a design decision first:** paginate everything? filter to traded series? sort by volume/liquidity? Then implement with a test against the captured real-data shapes. Determines what data the whole downstream system sees.
- [ ] **Quick adjacent win:** add `logging.basicConfig(level=INFO)` (or uvicorn `--log-level info`) so tick_poller's own poll-count logs are visible in the pod.

---

## 📊 Phase status at a glance

| Phase | Description | v2 ref | Status |
|---|---|---|---|
| **Phase 0** | Keep the lights on (old bot paused) | §11 | ✅ Active |
| **Phase 1** | Infrastructure foundation | §05, §11 | 🟢 11.5 / 12 (effectively complete) |
| **Phase 2** | Core data layer (data / oms / pms) | §04, §05, §06, §07 | 🟡 data-svc LIVE; oms/pms next |
| **Phase 3** | First strategy end-to-end (paper) | §08 | ⚪ Pending |
| **Phase 4** | Go live with TIMELY only | §09 | ⚪ Pending |
| **Phase 5** | Port remaining strategies | §10 | ⚪ Pending |
| **Phase 6** | Hardening + MCP integration | §12 | ⚪ Pending |
| **Phase 7** | Research & growth | §13 | ⚪ Pending |

**Total realistic timeline: 5-6 months calendar, evenings/weekends.**

---

## 🟢 Phase 1 — Infrastructure foundation (11.5 / 12) → v2 §05, §11

- [x] Task 1 — Kubernetes cluster (`midas-prod`, LON1, 3 nodes)
- [x] Task 2 — Managed Postgres (3 logical DBs) — *cross-DB denial check deferred to Phase 2*
- [x] Task 3 — Managed Redis
- [x] Task 4 — GitHub Actions CI (build + lint + test, branch protection)
- [x] Task 5 — Deploy-repo decision (in-tree `deploy/`)
- [x] Task 6 — Argo CD (GitOps, app-of-apps)
- [x] Task 7 — sealed-secrets controller — *proven on real Kalshi creds, session 8*
- [x] Task 8 — Credentials into sealed-secrets — *Kalshi creds sealed, session 8*
- [x] Task 9 — NATS — *live; Argo app cosmetically OutOfSync (immutable StatefulSet field)*
- [x] Task 10 — LGTM observability — *live; kube-state-metrics 0/1 is a carry item*
- [x] Task 11 — Hello-world end-to-end deploy (hello-svc)
- [~] Task 12 — Runbook — *started (`docs/RUNBOOK.md`); polish remaining = the 0.5*

---

## 🟡 Phase 2 — Core data layer → v2 §04, §05, §06, §07

### ✅ data-svc — LIVE (8/8 pieces, session 8) → v2 §07
- [x] Pieces 1–6 (Kalshi client, NATS publisher, tick poller, settings/entrypoint, Dockerfile + GHA, K8s manifests)
- [x] Piece 7 — sealed Kalshi credentials
- [x] Piece 8 — Argo Application + first deploy
- [x] Field-mapping fix (read `*_dollars`/`*_fp`, parse strings, dollars→cents) — verified, 161 tests green, ticks confirmed on NATS
- [ ] **Market selection** (the Right-now item above) → v2 §07
- [ ] Logging visibility one-liner
- [ ] `tick_at` → broker time (deferred to Phase 5 websocket migration)
- [ ] Account-data adapter (positions/fills) — later in Phase 2

### ⚪ oms-svc → v2 §04
- [ ] Event-sourced order log against `oms_db`
- [ ] Deploy to `trading-paper` namespace

### ⚪ pms-svc → v2 §04
- [ ] Event-sourced portfolio log against `pms_db`
- [ ] Deploy to `trading-paper` namespace

### ⚪ Phase 2 verification → v2 §05
- [ ] End-to-end: data-svc ticks visible in Grafana
- [ ] Event-sourcing proof: inject a deposit event, verify bankroll projection updates
- [ ] Wire reconciliation jobs to scheduler (Lesson 2)
- [ ] Execute cross-DB denial check carried from Phase 1 Task 2

---

## ⚪ Phase 3 — First strategy end-to-end (paper) → v2 §08
- [ ] Anthropic adapter in data-svc (AI edge detection)
- [ ] risk-svc (the gate stack, one canonical implementation — Lesson 5)
- [ ] strategy-timely (first strategy service)
- [ ] ems-svc paper mode (simulated fills)
- [ ] Full distributed trace of one bet in Grafana Tempo

---

## ⚪ Phase 4 — Go live with TIMELY only → v2 §09
- [ ] ems-svc live mode (real Kalshi orders)
- [ ] telegram-svc (basic alerting)
- [ ] Reconciliation jobs in OMS + PMS
- [ ] Deploy to `trading-prod`; run tiny bankroll 2-3 weeks
- [ ] **Old bot officially retired**

---

## ⚪ Phase 5 — Port remaining strategies → v2 §10
- [ ] strategy-midsel; strategy-arb (+ Polymarket adapter in data-svc)
- [ ] reporting-svc; FADHYPE / NICHDOM prompt strategies in AI edge detector

---

## ⚪ Phase 6 — Hardening + MCP → v2 §12
- [ ] mcp-svc (read → simulate → write tools with auth)
- [ ] Failure-scenario stress tests; runbooks; alertmanager rules

---

## ⚪ Phase 7 — Research & growth → v2 §13
- [ ] Experimental strategy services in paper; Bayesian-Kelly sizing experiment; new data sources

---

## 🚧 Carry items

| Item | Why it matters | When |
|---|---|---|
| **data-svc market selection** | Determines what data the whole system sees | Next session (highest value) |
| tick_poller logging one-liner | Pod's own logs currently dropped | Next session (quick) |
| `tick_at` → broker time | Accurate event timing | Phase 5 (websocket) |
| kps + nats Argo OutOfSync | DOKS quirks, cosmetic | Phase 1 cleanup |
| kube-state-metrics 0/1 Ready | Observability gap | Phase 1 cleanup |
| Stale argocd-initial-admin-secret | Tidiness/security | When convenient |
| Postgres + Redis password rotation | Security hygiene | When convenient |
| gh token read:packages scope | Lets us query GHCR directly | When convenient |
| Bump GHA action versions | Node 20 deprecation | Before 2026-06-02 |
| DO API token expires | doctl stops working if expired | ~July 27, 2026 (remind ~July 20) |
| Cross-DB denial check | Postgres role isolation | Phase 2 |
| `docs/ARCHITECTURE.md` is a stub | Fill as services come online | Phase 2+ |

---

## 💡 Working agreements (read every session)

1. **Filippo says when to stop.** Claude never asks "should we stop?"
2. Claude pushes back on shortcuts that violate the 10 constraints — name it, offer the alternative, ask whether to proceed.
3. Decisions inline; documents follow.
4. Verify before commit.
5. Never paste passwords/tokens in chat.
6. One visible win per week minimum.
7. Migration goal: same behavior, new architecture — behavioral changes are separate tested PRs.
8. Always read prior session-close docs before generating new ones.

---

## 📊 By the numbers (current)

- **Commits on main:** 67 · **HEAD:** `00ea987`
- **Phase:** 1 effectively complete (11.5/12); Phase 2 underway
- **Tests:** 161 passing
- **Services running:** 1 trading service (data-svc) + Phase 1 infra + hello-svc
- **Cloud cost:** ~$130 / month (target &lt;$150)
- **Last session:** May 27, 2026 (session 8, ~4h overnight, 4 commits) — data-svc live + field-mapping fix
