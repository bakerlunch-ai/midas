# Midas — Living TODO

> **Updated:** May 28, 2026 (end of session 9)
> **Format:** Living checklist. Updated at end of every session.
> **Aligned with:** `Bot_Architecture_v2_Professional_Grade_April26_2026.html` §11 (8-phase roadmap) and `docs/PHASE_1_PLAN.md`.
> **Pair this with:** `docs/PROJECT_HANDOFF.html` (current state), `docs/JOURNEY.md` (the arc), `docs/SESSION_HISTORY.md` (audit trail).

---

## 🎯 Right now — Next session opens here

- [ ] **IMPLEMENT data-svc market selection** → v2 §07. **Design is decided (session 9):** paginate ALL open Kalshi markets (stay blind to nothing) → SKIP any that fail our rules (rules TBD) → liquidity is a FIRST-CLASS signal (critical for trading, especially arb — need real two-sided books on both legs). Implement test-first against captured real-data shapes. Verify against the now-visible `published=N skipped=N` poll logs in the pod.

---

## 📊 Phase status at a glance

| Phase | Description | v2 ref | Status |
|---|---|---|---|
| **Phase 0** | Keep the lights on (old bot paused) | §11 | ✅ Active |
| **Phase 1** | Infrastructure foundation | §05, §11 | ✅ 12/12 done |
| **Phase 2** | Core data layer (data / oms / pms) | §04, §05, §06, §07 | 🟡 data-svc LIVE + observable; oms/pms next |
| **Phase 3** | First strategy end-to-end (paper) | §08 | ⚪ Pending |
| **Phase 4** | Go live with TIMELY only | §09 | ⚪ Pending |
| **Phase 5** | Port remaining strategies | §10 | ⚪ Pending |
| **Phase 6** | Hardening + MCP integration | §12 | ⚪ Pending |
| **Phase 7** | Research & growth | §13 | ⚪ Pending |

**Total realistic timeline: 5-6 months calendar, evenings/weekends.**

---

## 🟡 Phase 2 — Core data layer → v2 §04, §05, §06, §07

### 🟢 data-svc — LIVE + observable → v2 §07
- [x] Pieces 1–8 (built, deployed, verified — session 8)
- [x] Field-mapping fix (read `*_dollars`/`*_fp`, parse strings, dollars→cents) — 161 tests green, ticks confirmed (session 8)
- [x] Logging visibility — `logging.basicConfig` so poll-cycle logs reach `kubectl logs` (session 9, `d605909`)
- [ ] **Market selection** — DESIGN DECIDED, implement next: ingest-all → rule-filter → liquidity-weighted → v2 §07
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
| **data-svc market selection (implement)** | Determines what data the whole system sees; liquidity critical for arb | Next session (highest value) |
| **Harden CI** — branch protection ($16/mo Team plan); red-CI alerting (a way to KNOW the gate broke); document CI scope | CI was silently red for ~6 commits (May 21–27) and nothing told us — the gate needs a watcher | Soon |
| **Bump GHA action versions** (Node 20 deprecation) | GHA runs will break when Node 20 actions are removed | Before 2026-06-02 |
| Tier-2 CI: mypy, coverage, container image scanning | More bug-catching, but adds friction | Phase 3 (when strategies + real money raise value) |
| `tick_at` → broker time | Accurate event timing | Phase 5 (websocket) |
| kps + nats Argo OutOfSync | DOKS quirks, cosmetic | Phase 1 cleanup |
| kube-state-metrics 0/1 Ready | Observability gap | Phase 1 cleanup |
| Stale argocd-initial-admin-secret | Tidiness/security | When convenient |
| Postgres + Redis password rotation | Security hygiene | When convenient |
| gh token read:packages scope | Lets us query GHCR directly | When convenient |
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
9. **A green Build is not a green CI.** Check CI status (lint + test), not just that deploys are working.

---

## 📊 By the numbers (current)

- **Commits on main:** 71 · **HEAD:** `d605909`
- **CI:** green (lint + test both run and pass on every push) — restored session 9 after ~6 commits of silent red
- **Phase:** 1 done (12/12); Phase 2 underway (data-svc live + observable)
- **Tests:** 161 passing (now verified by CI, not just locally)
- **Services running:** 1 trading service (data-svc) + Phase 1 infra + hello-svc
- **Cloud cost:** ~$130 / month (target &lt;$150)
- **Last session:** May 28, 2026 (session 9, ~1.5h, 3 commits) — CI restored + logging fix
