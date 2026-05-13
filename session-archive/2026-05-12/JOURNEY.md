# Midas — The Journey

> **What this document is:** the narrative arc connecting all 8 phases. Every phase exists because of the previous one and unlocks the next. This is the "why we're building it in this order" doc.
>
> **Read alongside:** `Bot_Architecture_v2_Professional_Grade_April26_2026.html` (the master plan), `PROJECT_HANDOFF.html` (current state), `TODO.md` (live checklist).
>
> **Updated:** May 12, 2026 (end of session 6)

---

## The goal in one paragraph

We are rebuilding a Kalshi prediction-market trading bot from scratch as a multi-service event-driven system. The previous bot grew to ~5,300 lines in one Python file with structural bugs (mutable bankroll, dead reconciliation, dead strategies, magic numbers everywhere). The audit synthesis documented those failures. The architecture v2 document committed to a hedge-fund-style separation of concerns: data ingest, strategy logic, risk gates, order management, execution, and portfolio tracking, each a separate service communicating over NATS JetStream with event-sourced ledgers in Postgres. Midas is the deliberate slow-and-correct rebuild. We move forward one win per week minimum and accept a 5-6 month calendar timeline for Phases 1–6.

---

## Dependency chain

```
Phase 0 (lights on)
   ↓
Phase 1 (infra foundation) ──────────► ✅ DONE (May 12, end of session 6)
   ↓
Phase 1.5 (architectural cleanup)     ✅ 3/3 closed; 5 minor carry items remain
   ↓
Phase 2 (data layer: data-svc, oms-svc, pms-svc) ──► you are here
   - Event vocabulary: ✅ 7/7 types defined
   - Services: 0/3 built
   ↓
Phase 3 (first strategy paper-traded end-to-end)
   ↓
Phase 4 (live with TIMELY only, tiny bankroll)
   ↓
Phase 5 (port remaining strategies)
   ↓
Phase 6 (hardening + MCP for AI agents)
   ↓
Phase 7 (research, ongoing forever)
```

Each arrow is a real dependency, not a preference. You cannot build a strategy service without an event bus to publish on. You cannot publish events without a deployed event bus. You cannot deploy an event bus without a cluster to deploy it into. You cannot write events that services agree on without a defined schema. The order isn't bureaucracy — it's the actual shape of the build.

---

## Phase 0 — Keep the lights on

**What it is:** the old Kalshi bot remains paused with audit fixes documented but not applied unless trading absolutely needs to resume. We treat it as legacy reference, not active dev.

**Why it exists:** so we can build Midas without the pressure of also keeping a live system alive. The old bot is paused, so trading P&L is zero — but learning from its bugs is the whole reason Midas exists.

**Why it has to come first:** if we tried to migrate while still actively patching the old bot, every Midas decision would compete with old-bot firefighting and we'd never converge.

**What it enables:** undivided attention on the rebuild.

**v2 architecture reference:** §11 (8-phase migration roadmap), Phase 0.

---

## Phase 1 — Infrastructure foundation ✅ DONE

**What it is:** an empty cluster with everything a real service would need to run. Cluster, databases, message bus, observability, GitOps, sealed-secrets, CI/CD, and a smoke service that proves all of those are wired together correctly.

**Why it exists:** Phase 2's services (data-svc, oms-svc, pms-svc) all assume there's a Kubernetes cluster to deploy into, a Postgres to write events to, a Redis to cache against, a NATS to publish events on, and an observability stack to see what they're doing. Without Phase 1, every Phase 2 service would have to bootstrap its own infrastructure, and we'd repeat the old bot's mistake of tangling app code with infra.

**Why it has to come after Phase 0:** the old bot's pause gave us the head-space to design Phase 1 deliberately. The kitchen analogy: Phase 1 is the building's electrical, plumbing, and gas — wired up before any chef walks in. Phase 2 is the chefs.

**What it enables:** a Phase 2 service can `kubectl apply` and immediately have logs flowing to Loki, traces to Tempo, metrics to Prometheus, secrets via sealed-secrets, deployments via Argo CD (now via app-of-apps), and events publishable on NATS — without needing to build any of that itself.

**v2 architecture reference:** §05 (cluster), §06 (data plane: Postgres + Redis), §07 (NATS JetStream event bus), §08 (LGTM observability), §09 (GitOps + sealed-secrets), §10 (CI/CD).

**Status as of session 6:** 12/12 tasks done. Task 12 (RUNBOOK.md) closed Phase 1 at the start of session 6.

---

## Phase 1.5 — Architectural cleanup (discovered in session 6) ✅ 3/3

**What it is:** three architectural problems discovered while verifying Phase 1's Task 10 (LGTM observability). None were visible from Argo CD's "Synced+Healthy" status — they only surfaced when we actually tried to use the system end-to-end.

**The three problems:**

1. **Grafana datasources were incomplete** — only 2 of 4 (Prometheus + Alertmanager). Loki and Tempo were running but invisible to the dashboard. Fixed by appending datasource entries to the kube-prometheus-stack Helm values (commit `c04eed4`) and patching the live ConfigMap directly when DOKS apiserver instability blocked the Argo sync.

2. **No app-of-apps reconciling infra YAML** — every YAML change to `deploy/applications/` to date had been manually `kubectl apply`'d. Git and cluster were drifting silently; Argo's "Synced" only meant "cluster matches what was last applied," not "cluster matches git." Fixed by shipping `deploy/applications/app-of-apps.yaml` (commit `d394254`) — one Argo Application watching the whole folder, managing itself recursively. Bootstrap-applied once; self-sustaining from then on.

3. **No log shipper deployed** — Loki was running and ready, but nothing was sending logs to it. Took three iterations to get right: v1 (commit `8e192c7`, K8s-API-based) crushed single-binary Loki by backfilling 3+ days from epoch; v2 (commit `7216a72`) switched to file-based reading `/var/log/pods/*` with `tail_from_end = true`; v3 (commit `6d25248`) added a drop relabel rule for kube-system + monitoring namespaces. Each iteration deployed via the GitOps pipeline shipped in Problem 2.

**Why it exists:** because "Synced + Healthy" in Argo CD means "the cluster matches what Argo last applied," not "the cluster matches git" and not "the system actually does its job." Phase 1.5 is the audit gap that Phase 2 would have hit immediately — and that we caught one session before it would have bitten us.

**Why it has to come before Phase 2:** Phase 2 services need (a) a working GitOps deploy path so we don't repeat the manual-apply pattern, (b) actual log shipping so services are observable from day one, (c) all four datasources in Grafana so the team can debug what's flowing.

**What it enables:** every commit to `deploy/applications/` going forward now flows automatically; every pod's logs are queryable in Grafana by namespace/pod/container/app/node within seconds; the team can debug Phase 2 services without setting up per-service log shipping.

**Remaining carry items (5, all minor, none blocking Phase 2):**
- kube-prometheus-stack Argo Application stuck OutOfSync (functional fix already live; bookkeeping stuck behind DOKS apiserver instability)
- nats Argo Application OutOfSync (cosmetic, pre-existing, ~10 min fix)
- DigitalOcean apiserver instability (file DO support ticket — kube-state-metrics restart count grew 28 → 47 over session)
- Postgres oms_user + Redis password rotation (leaked in chat May 9; VPC-only mitigates external exposure)
- Redis security patch flagged by DigitalOcean (apply in maintenance window)

**v2 architecture reference:** §08 (observability — datasources, log shipping), §09 (GitOps — app-of-apps closes the auto-reconcile loop).

---

## Phase 2 — Core data layer

**What it is:** the three foundational services — data-svc (ingests Kalshi market data + FRED + AI edge analysis), oms-svc (event-sourced order log against `oms_db`), pms-svc (event-sourced portfolio log against `pms_db`). The bot-events package gets fleshed out with all the real event types.

**Why it exists:** these three services are the substrate every strategy service runs on. A strategy reads market ticks from data-svc, decides to bet, sends an OrderPlaced event, and watches OrderFilled / PositionClosed events come back. If those three services don't exist, no strategy can be written.

**Why it has to come after Phase 1 (and 1.5):** event-sourced services need (a) a working event bus (Phase 1 §07), (b) reliable databases with sealed credentials (Phase 1 §06 + §09), (c) observability so we can see them working (Phase 1 §08 + Phase 1.5 log shipper), (d) auto-deploy from git so we're not manually applying changes for every iteration (Phase 1.5 app-of-apps), (e) a shared schema for the events they exchange (Phase 2 vocabulary, shipped session 6).

**What it enables:** Phase 3 can write a single strategy service that reads market data, makes decisions, and watches its orders flow through a real OMS into a real PMS — all in paper mode, all observable, all using the event vocabulary defined in session 6.

**Session 6 milestone — Phase 2 event vocabulary defined (7/7):**

| Event | Subject | Emitted by | Tests |
|---|---|---|---|
| `MarketTickEvent` | `events.market.tick.<exchange>.<ticker>` | data-svc | 12 |
| `OrderPlacedEvent` | `events.order.placed.<exchange>.<ticker>` | oms-svc | 17 |
| `OrderFilledEvent` | `events.order.filled.<exchange>.<ticker>` | oms-svc | 16 |
| `OrderCancelledEvent` | `events.order.cancelled.<exchange>.<ticker>` | oms-svc | 13 |
| `PositionOpenedEvent` | `events.position.opened.<exchange>.<ticker>` | pms-svc | 16 |
| `PositionClosedEvent` | `events.position.closed.<exchange>.<ticker>` | pms-svc | 18 |
| `BankrollChangedEvent` | `events.bankroll.changed` | pms-svc | 16 |

Combined with BaseEvent (5 tests) and HeartbeatEvent (7 tests), the bot-events package now has 9 types and 120 passing tests.

Key event-sourcing discipline encoded in the schemas: order-level facts (side, direction, limit_price) live on OrderPlacedEvent only and are joined via `exchange_order_id` to fill/cancel events. Bankroll uses an event-sourced delta + checksum pattern with no mutable balance field (binding constraint #1). Realized P&L is pre-computed on PositionClosedEvent in dollars (signed for losses), with pms-svc as the canonical source. Decimal-in-cents for prices, Decimal-in-dollars for money. No floats.

**Phase 2 services remaining (0/3):**
- data-svc (Kalshi adapter, emits MarketTickEvent)
- oms-svc (event-sourced order log against `oms_db`)
- pms-svc (event-sourced portfolio log against `pms_db`, emits PositionOpened/Closed + BankrollChanged)

**v2 architecture reference:** §02 (service map), §03 (event sourcing), §04 (bot-events package — completed in session 6), §06 (database schemas).

---

## Phase 3 — First strategy end-to-end (paper)

**What it is:** TIMELY (the time-decay heavy-favorite strategy from the old bot) runs in paper mode against real Kalshi market data. It reads ticks from data-svc, proposes orders through risk-svc (gate stack), they hit oms-svc, get simulated-filled by ems-svc, and pms-svc records the bet. Grafana Tempo shows the full distributed trace of one bet.

**Why it exists:** before any real money is on the line, we validate the entire architecture with a real workload. If something's structurally wrong with the event flow, this is where it surfaces — cheaply, with no cash at risk.

**Why it has to come after Phase 2:** strategies need data-svc, oms-svc, and pms-svc to exist. Without those, "strategy" is just a function with nothing to read or write.

**What it enables:** Phase 4 to flip the same architecture to live mode with confidence.

**v2 architecture reference:** §02 (strategy service interface), §11 (Phase 3).

---

## Phase 4 — Go live with TIMELY only

**What it is:** ems-svc gets a live mode (real Kalshi orders) alongside its paper mode. Tiny bankroll ($50–$100) for 2–3 weeks. Daily reconciliation jobs scheduled. Telegram alerts wired. The old bot is officially retired.

**Why it exists:** prove the new architecture handles real fills, real reconciliation, real money — but at a scale where a bug costs us coffee, not rent.

**Why it has to come after Phase 3:** Phase 3 validated the event flow. Phase 4 only swaps the executor (paper → live). Everything else stays the same.

**What it enables:** Phase 5's strategy ports happen with confidence in the runtime.

**v2 architecture reference:** §10 (deployment), §11 (Phase 4), §12 (live trading runbook).

---

## Phase 5 — Port remaining strategies

**What it is:** strategy-midsel (the exit strategy), strategy-arb (cross-platform Kalshi/Polymarket arb, requires a Polymarket adapter in data-svc), reporting-svc with daily/weekly reports, and prompt-fragment strategies (FADHYPE, NICHDOM) added to the AI edge detector.

**Why it exists:** functional parity with the old bot's actual capabilities, but with all the new architecture's reliability, observability, and testability gains.

**Why it has to come after Phase 4:** TIMELY trading live in Phase 4 is the smoke test for the runtime. If it survives 2–3 weeks live, we trust the runtime enough to put more strategies on top.

**What it enables:** Phase 6's hardening pass has a real workload to harden against.

**v2 architecture reference:** §11 (Phase 5).

---

## Phase 6 — Hardening + MCP integration

**What it is:** mcp-svc (exposes the bot to Claude as a first-class system via Model Context Protocol — read tools first, simulate tools next, write tools with auth last). Stress-test failure scenarios: kill ems-svc mid-fill, kill the database, kill NATS, see what happens. Write runbooks for each known failure mode. Set up alerting in Prometheus alertmanager.

**Why it exists:** make it production-grade. Operationally, not just functionally.

**Why it has to come after Phase 5:** can't harden a system that doesn't have all its parts yet.

**What it enables:** Phase 7's research becomes safer because failures are caught and recoverable.

**v2 architecture reference:** §13 (MCP integration), §14 (operational hardening).

---

## Phase 7 — Research & growth

**What it is:** experimental strategy services in paper mode, Bayesian-Kelly sizing experiment (paper first, then prod if it outperforms), new data sources as MCPs or direct adapters, new strategies as new services.

**Why it exists:** this is how the bot grows over years, not weeks.

**Why it has to come after Phase 6:** experiments need a stable platform underneath them.

**What it enables:** the bot keeps getting better forever.

**v2 architecture reference:** Section 11, Phase 7. No end date.

---

## Where we are right now

| Metric | Value |
|---|---|
| Current phase | Phase 2 (core data layer) — event vocabulary done, services pending |
| Phase 1 progress | **✅ 12 / 12 tasks complete (closed end of session 6)** |
| Phase 1.5 progress | **✅ 3 / 3 architectural problems closed; 5 minor carry items remain** |
| Phase 2 progress | Event vocabulary: **7/7 types defined**. Services: 0/3 built. |
| Calendar elapsed | ~13 days (Apr 29 → May 12) |
| Time invested | ~25 hours across 6 sessions |
| Cloud cost | ~$130 / month (target: <$150) |
| Commits on main | 41 (28 going into session 6 → 13 added tonight) |
| Latest commit | `d23d13f` — feat(bot-events): add BankrollChangedEvent — closes Phase 2 event vocabulary |
| Tests | 120 passing (24 → 120 in session 6) |
| Services running | 1 application service (hello-svc) + cluster infrastructure (Argo CD, app-of-apps, sealed-secrets, NATS, kube-prometheus-stack, Loki, Tempo, **Alloy log shipper — new**) |
| Argo Applications | 9 total (7 Synced+Healthy, 2 OutOfSync but cosmetic) |

**End-of-session 6 milestone:** Phase 1 is officially closed. The cluster genuinely has all the infrastructure a real service needs (cluster, DBs, secrets, GitOps via app-of-apps, observability with logs now flowing, message bus). Phase 2's event vocabulary — the language the next three services will speak — is fully defined and tested. The next session opens at the start of real service work: data-svc.

**Update cadence:** this file is updated when phase progress materially changes (a phase completes, a task count shifts) or when a phase's "what it enables" section changes because of new findings. Not every session touches it. Session 6 touched it because Phase 1 closed, Phase 1.5 was discovered and resolved, and Phase 2 entered active development.
