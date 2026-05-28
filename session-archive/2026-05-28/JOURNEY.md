# Midas — The Journey

> **What this doc is:** the narrative arc. `PROJECT_HANDOFF.html` tells you *what's true right now*; this tells you *why we're building the 8 phases in this order, and what each one unlocks*. The master plan is `Bot_Architecture_v2_Professional_Grade_April26_2026.html` (referenced as "v2 §X").
>
> **Updated:** May 28, 2026 (end of session 9) — when phase progress materially shifts.

---

## The goal, in one paragraph

Rebuild a Kalshi prediction-market trading bot as a multi-service, event-driven system that does *not* repeat the structural failures of the old bot (bankroll that only went up, reconciliation that never ran, dead code, magic numbers, untested growth). The new system separates concerns the way a hedge fund does — data, orders, portfolio, risk, execution as distinct services talking over an event bus — so each piece is independently testable, observable, and replaceable. We build it slowly and deliberately, proving each layer works before stacking the next on top.

---

## The dependency chain

```
Phase 0 ──> Phase 1 ──> Phase 2 ──> Phase 3 ──> Phase 4 ──> Phase 5 ──> Phase 6 ──> Phase 7
(lights on) (infra)    (data layer) (1 strat   (go live    (port all   (harden +  (research,
                                     paper)     TIMELY)     strategies) MCP)       forever)

Each arrow is a hard dependency. You cannot run a strategy (3) without a data
backbone (2). You cannot build the data backbone (2) without infrastructure to
run it on (1). You cannot trust real money (4) until you have watched a strategy
work end to end in paper (3).
```

---

## Phase by phase

### Phase 0 — Keep the lights on
**What it is:** the old bot, paused. **Why it exists:** so there's a fallback if trading must resume mid-migration — done on the *old* bot with audit fixes, never the half-built new one. **Why first:** it removes time pressure from the rebuild. **Unlocks:** the freedom to build Midas slowly and correctly. **v2 ref:** §11.

### Phase 1 — Infrastructure foundation
**What it is:** an empty but fully-wired Kubernetes cluster — GitOps (Argo), secrets (sealed-secrets), event bus (NATS), databases (Postgres/Redis), observability (LGTM), and a hello-world service that deploys end to end. **Why it exists:** every service needs somewhere to run, a way to be deployed, a way to keep secrets, a way to talk, and a way to be watched. **Why it has to come before Phase 2:** you cannot deploy a real service onto infrastructure that doesn't exist. **Unlocks:** the ability to ship any service by adding one Argo Application file. **v2 ref:** §05, §11.

> **Session 8 milestone:** Phase 1 is effectively complete (11.5/12). The remaining 0.5 is cleanup — two cosmetically-OutOfSync Argo apps and runbook polish. data-svc (a Phase 2 service) was built and deployed during this window because it was the natural first *real* service to prove the whole chain end to end.

### Phase 2 — Core data layer
**What it is:** the three services that form the data backbone — **data-svc** (ingests market data from Kalshi, publishes ticks), **oms-svc** (event-sourced order log), **pms-svc** (event-sourced portfolio log). **Why it exists:** a strategy is worthless without correct market data flowing in and trustworthy ledgers recording what happened. **Why it has to come after Phase 1:** these services need the cluster, the event bus, the databases, and the secrets pantry to exist first. **Unlocks:** a system that ingests real market data and keeps event-sourced books — the input and the memory every strategy depends on. **v2 ref:** §04, §05, §06, §07.

> **Session 8–9 milestone:** **data-svc is LIVE, verified, and now observable** — the first real Midas service in production. It polls Kalshi and publishes correct `MarketTickEvent`s to NATS. Session 8 caught and fixed (test-first) a field-mapping bug that had it silently publishing nothing — exactly the Lesson-8 trap the rebuild exists to prevent. Session 9 made the poller audible: its poll-cycle logs (`published=N skipped=N`) now stream in `kubectl logs`, turning the one open design question into something we can watch live. That question — *which* markets data-svc should track — was decided in session 9 (ingest all → skip those failing our rules → liquidity as a first-class signal) and is the session-10 implementation opener. oms-svc and pms-svc are next.

### Phase 3 — First strategy end to end (paper)
**What it is:** TIMELY running the whole loop in paper — market arrives → strategy proposes → risk approves → OMS records → EMS simulates a fill → PMS records the bet — with a full distributed trace visible. **Why it exists:** to validate the entire architecture with a real workload before any real money. **Why after Phase 2:** a strategy consumes the data and ledgers Phase 2 builds. **Unlocks:** confidence that the architecture works end to end. **v2 ref:** §08.

### Phase 4 — Go live with TIMELY only
**What it is:** real money, one strategy, tiny bankroll. **Why it exists:** the smallest possible real-money test. **Why after Phase 3:** never risk money on a path you haven't watched work in paper. **Unlocks:** retiring the old bot. **v2 ref:** §09.

### Phase 5 — Port remaining strategies
**What it is:** the rest of the old bot's real functionality (MIDSEL, arb, the AI edge prompts), each going paper → prod. **Why after Phase 4:** prove the live path with one strategy before adding more. **Unlocks:** feature parity with the old bot, on better foundations. **v2 ref:** §10.

### Phase 6 — Hardening + MCP
**What it is:** production-grade reliability, failure-mode testing, runbooks, alerts, and an MCP service exposing the bot to Claude as a first-class system. **Why after Phase 5:** harden what's complete. **Unlocks:** a system you can trust unattended. **v2 ref:** §12.

### Phase 7 — Research & growth
**What it is:** ongoing experimentation — new strategies, new data sources, new sizing models — always paper-first. **Why last / forever:** it's how the bot grows once it's solid. **v2 ref:** §13.

---

## Where we are right now

- **Phase:** 1 complete (12/12); Phase 2 underway — **data-svc shipped, verified live, and observable.**
- **Services live:** 1 (data-svc), plus all Phase 1 infrastructure + hello-svc.
- **Commits on main:** 71 · **HEAD:** `d605909` · **Tests:** 161 passing (now verified by CI).
- **CI:** green — restored in session 9 after ~6 commits of silent red (the gate had been failing on lint debt, blocking tests from running, while the independent Build workflow kept deploys flowing).
- **Cloud cost:** ~$130/month (target &lt;$150).
- **Time invested:** 9 sessions across roughly one month calendar time (evenings/overnight).
- **The headline:** the first real service is live, proven, and now audible — and the safety net that verifies everything we ship is working again. Next: implement the decided market-selection design (ingest-all → rule-filter → liquidity-weighted), then build oms-svc and pms-svc.

---

## Update cadence

Update this file when phase status materially changes — a phase completes, a major service ships, or the "where we are right now" facts shift. Not every session touches it; session 8 did because data-svc going live is a real Phase 2 milestone, and session 9 did because restoring the CI gate (after it had been silently bypassed for a week) is a foundational change to how reliably everything else gets verified — the Lesson-10 backbone of the whole rebuild.
