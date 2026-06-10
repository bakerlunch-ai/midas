# Midas — the Journey

**Updated:** 2026-06-09 (end of session 10)
**HEAD:** `cd7c3d2`
**Where we are:** Phase 1, ~10/12 tasks done. Two-loop market selection shipped in code, deployed to cluster, now in real-data calibration phase.

---

## Goal in one paragraph

Build a professional-grade, multi-service, event-driven prediction-market trading system from scratch — explicitly avoiding the patterns that broke the legacy bot. Not a rewrite of the old code, a structural rebuild against a 14-section v2 architecture document with hedge-fund-style OMS/EMS/Risk separation. The legacy bot had 8 strategies (2 dead), magic numbers everywhere, mutable bankroll, no schema, no tests. Midas has tests as a CI gate, config in env vars, events as the only state mutation, services as bounded contexts. ~5–6 months calendar across 8 phases.

---

## Dependency chain

```
Phase 0 ──► Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4 ──► Phase 5 ──► Phase 6 ──► Phase 7
  │            │            │            │            │            │            │            │
  Keep         Cluster      OMS/PMS      Risk         Strategy    Websocket    First       Real
  legacy       up + data    order +      gates +      framework    migration    strategy    money
  alive        flowing      positions    halts        (pluggable)               on paper    on first
                                                                                            strategy
```

Each phase enables what comes after. None can skip ahead. The whole point is to build deliberately so the trust we put in the final live-money trades is earned across this chain.

---

## Phase 0 — Keep the lights on (DONE)

**What it is:** Don't break the legacy bot while building Midas. The old `bot.py` / `shadow_bot.py` continues paper-trading until Midas replaces it.

**Why it exists:** We need a working legacy baseline to compare against, and we don't want to lose the small amount of real money trickling through while building. Also: the legacy bot is the source of "what was the field name again?" answers when Midas needs to ingest the same Kalshi shapes.

**Why it has to come first:** Without a stable legacy baseline, Midas would have to ship faster than its tests, which is exactly what broke the legacy bot.

**What it enables:** Time to build Midas right.

**v2 architecture reference:** §01 (motivation / scope)

---

## Phase 1 — Cluster up, data flowing (IN PROGRESS)

**What it is:** A Kubernetes cluster on DigitalOcean (London region, 3 nodes), running Argo CD for GitOps deploys, with the core infrastructure (NATS message bus, Postgres event store, Redis cache) and the first ingestion service (data-svc) reading Kalshi and publishing MarketTickEvents to NATS.

**Why it exists:** Every other service depends on data flowing. Strategies need market ticks to react to. OMS needs ticks to know what price to send orders at. Risk needs ticks to know what positions are worth. No data flow, no system.

**Why it has to come after Phase 0:** Building this in parallel with active legacy trading would risk breaking the legacy bot or being tempted to migrate it before Midas is ready.

**What it enables:** Phase 2 — OMS can start consuming MarketTickEvents to know when to place/modify orders.

**v2 architecture reference:** §03 (cluster), §04 (data-svc), §05 (NATS event bus), §07 (Postgres event store)

**Where we are right now (Phase 1 task list):**
- ✅ Cluster, Argo, NATS, Postgres, Redis deployed
- ✅ hello-svc as reference implementation
- ✅ data-svc skeleton + Kalshi RSA auth
- ✅ MarketTickEvent schema
- ✅ NATS publisher
- ✅ CI pipeline (lint + test on every push)
- ✅ **Two-loop market selection (session 10): shipped in code**
- 🔶 data-svc stable on cluster — blocked by startupProbe + max_pages calibration
- ⚪ Postgres event store schema (event_envelope)

---

## Phase 2 — OMS / PMS (PENDING)

**What it is:** Order Management Service places, modifies, and cancels orders on Kalshi (and later Polymarket). Position Management Service tracks open positions, computes P&L, and reconciles against broker state.

**Why it exists:** Without these, strategies can't actually trade. The legacy bot conflated order execution and position tracking; v2 separates them into bounded contexts so each can be reasoned about (and tested) independently.

**Why it has to come after Phase 1:** OMS needs MarketTickEvents to know current prices. PMS needs to write to the Postgres event store (which Phase 1 stands up).

**What it enables:** Phase 3 (Risk sits on top of position state). Phase 4 (strategies consume position events).

**v2 architecture reference:** §06 (OMS), §07 (PMS + event store)

---

## Phase 3 — Risk service (PENDING)

**What it is:** Centralized risk gates — exposure caps, weekly loss limits, contradictory-position prevention, per-ticker max entries. Subscribes to position events and order intent events; emits halt/allow decisions.

**Why it exists:** Binding constraint #5 — risk gates duplicated in eight places in the legacy bot. v2 has exactly one canonical implementation. Without this layer, strategies can't be trusted to police themselves.

**Why it has to come after Phase 2:** Needs PMS's position state to make decisions.

**What it enables:** Phase 6+ real-money trading. Without risk gates, real money is off the table.

**v2 architecture reference:** §08

---

## Phase 4 — Strategy framework (PENDING)

**What it is:** Pluggable strategy harness. Each strategy is a subclass with a fixed contract (subscribe to events, emit trade intents). `__init_subclass__` enforces registration so dead strategies can't exist (binding constraint #3).

**Why it exists:** Legacy bot's strategies were strings and string-keyed dicts. Half the strategies in the codebase weren't actually running. v2 makes the registration explicit at class-definition time.

**Why it has to come after Phase 3:** Strategies emit intents; risk decides. No risk service, no safe strategy execution.

**What it enables:** Phase 6 — running real strategies on paper.

**v2 architecture reference:** §09

---

## Phase 5 — Websocket migration (PENDING)

**What it is:** Migrate from REST polling (current data-svc) to Kalshi's websocket feed. Lower latency, lower API quota usage, more responsive.

**Why it exists:** Polling at 5s intervals is fine for development but won't scale to fast-moving markets in live trading. The current REST architecture is a deliberate first-version simplification.

**Why it has to come after Phase 4:** Strategies need to exist before low-latency data matters. Building websocket plumbing without consumers is premature.

**What it enables:** Phase 6/7 live trading with realistic data freshness.

**v2 architecture reference:** §10

---

## Phase 6 — First strategy on paper (PENDING)

**What it is:** One strategy running end-to-end on paper money: data-svc → strategy-svc → oms-svc → pms-svc → risk-svc. Likely a simple cross-venue arbitrage between Kalshi and Polymarket, or a Fed-decision time-decay play.

**Why it exists:** Proves the whole architecture wires up correctly before risking real capital. Surfaces any integration bugs.

**Why it has to come after Phase 5:** Strategies and data need to be production-shaped before this is a meaningful test.

**What it enables:** Phase 7 real money.

**v2 architecture reference:** §11

---

## Phase 7 — Real money on first strategy (PENDING)

**What it is:** Flip the switch. Same strategy, real positions, real P&L.

**Why it exists:** The whole point of the rebuild.

**Why it has to come after Phase 6:** Self-evident.

**v2 architecture reference:** §12

---

## Where we are right now

| Metric | Value |
|---|---|
| Current phase | Phase 1 (~10/12 tasks done) |
| Latest commit | `cd7c3d2` |
| Commits on main | 75 |
| Tests | 207 passing, lint clean |
| CI | Green on tip, both Commit A + B independently verified |
| Cluster cost | ~$130/month |
| data-svc deployed | New two-loop selection (ac7f99e), flaky on cluster |
| Time invested | ~10 working sessions |
| Calendar elapsed | ~6 weeks since v2 architecture finalized |

**What's blocking Phase 1 closure:**
1. data-svc startupProbe (cluster fix, not code)
2. Kalshi pagination scope (real universe is 20k+ markets, our 20-page cap truncates wrong)
3. Liquidity threshold tuning from real data

Once those three are addressed and data-svc is publishing a useful selected universe steadily, Phase 1 is done and we move to Phase 2 (OMS/PMS).

---

## Update cadence

This document is updated when phase progress materially shifts (a phase moves from pending→in-progress→done; "where we are right now" numbers change). Session reports and the TODO list are updated every session; JOURNEY.md is updated when the *story* changes, not the daily tasks.
