# Midas — The Journey

> **Purpose:** When you open the repo in October and ask "wait, why are we building this again?" — read this first.
>
> This document is the story of Midas, in plain English. It explains why each phase exists, what it enables, why the order matters, and how each piece fits into the v2 architecture's goal.
>
> **Pair this with:** `Bot_Architecture_v2_Professional_Grade_April26_2026.html` (the technical blueprint) and `docs/TODO.md` (the live checklist). This document tells you the *why*; those documents tell you the *what* and *when*.

---

## The Goal in One Paragraph

We're building a prediction-market trading bot good enough that a knowledgeable observer would call it professional work. The legacy bot we audited had structural bugs that made it fundamentally untrustworthy — bankroll figures that only went up, dead reconciliation code, strategies that didn't run, no test coverage, magic numbers everywhere. We're not patching that. We're rebuilding from scratch using the same vocabulary professional trading firms use: separate services for order management, portfolio management, execution, risk, strategy, data, and observability. Each service does one job. They communicate through events. The whole system is event-sourced — meaning the truth lives in an append-only log of what happened, not in mutable fields that can drift. The end state is a bot we trust enough to put real money behind, that we can grow over years without it collapsing under its own weight.

---

## The Arc — Why the Phases Are in This Order

Each phase exists because the next phase needs it. Skipping forward causes pain. Here's the dependency chain:

```
Phase 0 (legacy paused)  →  nothing's bleeding while we build
        ↓
Phase 1 (infrastructure) →  the platform services will run on
        ↓
Phase 2 (data layer)     →  the system can ingest and store
        ↓
Phase 3 (first strategy) →  the platform proves it works end-to-end (paper)
        ↓
Phase 4 (go live)        →  one strategy trades real money
        ↓
Phase 5 (port the rest)  →  the legacy bot can be retired
        ↓
Phase 6 (hardening)      →  the system survives bad days
        ↓
Phase 7 (research)       →  the system grows
```

Read each phase below as: **"what does this phase make possible that wasn't possible before?"**

---

## Phase 0 — Keep the Lights On

**Status: Active (ongoing)**

**What it is:** The legacy bot is paused. If we *do* trade during the Midas build, we do it on the old bot with audit fixes applied — never on the half-built new system.

**Why it exists:** Because rebuilding takes 5-6 months. We need a clear answer to "is the bot trading right now?" at any point during the build, and we need it to be a binary yes/no — not "kind of, on the new thing, in some half-deployed state." Phase 0 is the discipline of keeping the old and new strictly separated.

**What it enables:** Everything. Without this discipline, every Phase 1+ session would be derailed by "should we hot-patch the old bot real quick?" Now the answer is no.

**v2 architecture reference:** Section 11 (migration roadmap) explicitly carves this out as "the old system stays operational where needed — we don't break what works while building what's better."

---

## Phase 1 — Infrastructure Foundation

**Status: 9.5 of 12 tasks complete (~79%)**

**What it is:** Building the platform that every Midas service will run on. Cloud cluster, managed databases, message bus, observability, secrets management, GitOps deployment, CI/CD. Twelve concrete tasks.

**Why it exists:** Because professional trading systems aren't single Python files on a NAS. They're sets of small services that coordinate. That coordination requires real platform infrastructure: a way to run containers (Kubernetes), a way to deploy them safely (Argo CD), a way to keep secrets out of git (sealed-secrets), a way to see what's happening (LGTM stack), a way to send messages between services (NATS), and somewhere to store data (Postgres + Redis).

**Why it has to come first:** Phase 2 builds three Python services. Those services need somewhere to run, somewhere to store data, somewhere to log to, somewhere to read secrets from. If we built the services first, we'd have eight Python files on a laptop and no way to run them. So infrastructure first, services second.

**What we built across sessions 1-4 (April 29 → May 6, 2026):**
- **Task 1 (Kubernetes cluster):** Three nodes in London. Where every Midas service will run. → architecture v2 Section 7
- **Task 2 (Postgres + 3 logical DBs):** oms_db, pms_db, reporting_db — one per service that needs durable state. Logical separation enforces "each service owns its own data." → architecture v2 Section 6
- **Task 3 (Redis):** Short-lived state needs a fast in-memory store. Postgres is too slow for things like rate limits and idempotency keys. → architecture v2 Section 6
- **Task 4 (CI):** Tests must run automatically. The legacy bot's #1 lesson was "the bot grew faster than its tests." CI on every push closes that hole forever. → architecture v2 Section 4 (Lesson 10)
- **Task 5 (in-tree manifests):** Decided where Kubernetes manifests live. Two-person team — separate deploy repo would be ceremony without benefit.
- **Task 6 (Argo CD + GitOps):** The **loading dock**. Commit a manifest → Argo CD applies it → service runs in cluster. No manual `kubectl apply` for app deploys ever again. → architecture v2 Section 7
- **Task 7 (sealed-secrets):** The **locked supply room**. Encrypted credentials live in git, decrypted only by the cluster. Every Phase 2+ service can read database/API credentials safely. Round-trip verified end-to-end. → architecture v2 Section 7
- **Task 8 (4 real credentials sealed):** Postgres oms/pms/reporting users + Redis. Each service's database connection string now exists as a SealedSecret in `deploy/secrets/`, ready for Phase 2 services to mount via `envFrom`. → architecture v2 Section 6
- **Task 9 (NATS JetStream):** The **kitchen intercom**. 3-replica cluster with file-store persistence and durability proven (killed leader, message survived restart). This is *the* backbone of the event-sourced architecture — every state change flows through here, every service publishes to and subscribes from here. Without this, binding constraint #1 ("bankroll only goes up — use event sourcing") is impossible. → architecture v2 Section 5
- **Task 10 partial (Loki + Tempo):** Loki gives us "what did the bot say?" Tempo gives us "when service A called B which called C, where did time go and where did it fail?" Both running. → architecture v2 Section 7

**What still needs building (Tasks 10-finish, 11, 12):**
- **Task 10 finish (kube-prometheus-stack):** The metrics half of LGTM. Prometheus + Grafana + Alertmanager + exporters. Currently stuck on CRD bootstrap; Plan B documented for next session. **Not a Phase 2 blocker** — Phase 2 services can deploy without it; we'd just have reduced visibility until it lands.
- **Task 11 (hello-svc proof-of-life):** A tiny FastAPI service that connects to Postgres + Redis + NATS using the sealed credentials. This is the integration test that proves Phase 1 works end-to-end. If hello-svc starts cleanly, every Phase 2+ service can. **Highest-value remaining task in Phase 1.**
- **Task 12 (runbook):** `docs/RUNBOOK.md` — how to operate the cluster, where things live, how to seal new credentials, how to access Grafana once kps is fixed. Operational documentation is part of v2 §07's stack, not optional.

**v2 architecture reference:** Sections 6 (data stores), 7 (operational stack), 8 (observability), 11 (Phase 1 description).

---

## Phase 2 — Core Data Layer

**Status: Pending. ~3-4 weeks estimated.**

**What it is:** The first three real Midas services. `data-svc` (ingests market data from Kalshi). `oms-svc` (Order Management System — records every order proposal, approval, fill). `pms-svc` (Portfolio Management System — records every bankroll change, position, P&L). All event-sourced.

**Why it exists:** Because before we can trade, we have to be able to *see* the markets and *track* what we own. These three services are the data backbone. Everything in Phases 3+ either reads from or writes to them.

**Why it has to come after Phase 1:** All three services need the cluster (run them somewhere), Postgres (store events), Redis (cache hot data), NATS (publish events to other services), the LGTM stack (be observable), and Argo CD (deploy them). All built in Phase 1.

**Why event-sourced:** This is *the* design choice that prevents the legacy bot's #1 bug. The legacy bot stored bankroll as a number that mutable code paths updated. Some paths added; no paths subtracted. Bankroll only went up. Event sourcing means the bankroll is **never stored as a number** — it's computed by replaying every deposit, withdrawal, win, and loss event. There is no "decrement code path" because there is no stored balance to decrement. → architecture v2 Section 4 (Lesson 1)

**What this enables:** After Phase 2, we can run the data-svc and watch market ticks flow through. We can manually inject a test deposit event and see PMS compute the correct bankroll. We have working ledgers. We just don't have any *strategy* yet — that's Phase 3.

**v2 architecture reference:** Sections 5 (event-sourced architecture), 9 (data-svc design), 10 (OMS/PMS design), 11 (Phase 2 description).

---

## Phase 3 — First Strategy End-to-End (Paper)

**Status: Pending. ~2-3 weeks estimated.**

**What it is:** Plug the first strategy into the platform. `strategy-timely` proposes bets. `risk-svc` approves or denies them. `ems-svc` (Execution Management System) simulates fills against Kalshi market data. End-to-end, in paper mode (no real money).

**Why it exists:** Because before we trust any strategy with real money, we need to see one end-to-end with simulated money first. Phase 3 is where the architecture gets its first real workload.

**Why it has to come after Phase 2:** TIMELY needs to read market data (data-svc), propose orders (oms-svc), have risk evaluated (risk-svc), get fills (ems-svc), and have the result update bankroll (pms-svc). All those services must exist first.

**Why TIMELY first:** The legacy audit found TIMELY was the workhorse — most of the bot's actual bet placements came from it. Other strategies in the legacy bot were either dead code (XMKTARB, LNGSHOT) or prompt fragments (FADHYPE, NICHDOM). Starting with TIMELY proves the architecture works on the strategy that mattered most.

**What this enables:** A working bot, in paper mode. Distributed traces in Grafana showing a market tick flowing through data-svc → strategy-timely → risk-svc → oms-svc → ems-svc → pms-svc. End-to-end in seconds. The platform is real.

**v2 architecture reference:** Sections 11 (Phase 3 description), 12 (strategy service pattern).

---

## Phase 4 — Go Live with TIMELY Only

**Status: Pending. ~2-3 weeks estimated.**

**What it is:** Switch ems-svc from paper mode to live mode. TIMELY trades real money on Kalshi. Every other strategy stays off.

**Why it exists:** Because at some point the system has to face real markets, real fills, real slippage. Paper mode is honest, but it's not the same as real money. Phase 4 is where the rubber meets the road.

**Why it has to come after Phase 3:** Because we want to see the system work in paper before risking a dollar. Phase 3 proves the wiring is right; Phase 4 proves the wiring survives reality.

**Circuit breakers:** Start with a small bankroll cap ($50) as a circuit breaker. If something's wrong, $50 is the worst-case loss before someone notices. Increase the cap only after the metrics look healthy for two weeks.

**What this enables:** The first time Midas earns its keep. Also the first time we can compare Midas's per-bet decisions to what the legacy bot would have done — and start trusting the new system over the old one.

**v2 architecture reference:** Section 11 (Phase 4 description).

---

## Phase 5 — Port the Remaining Strategies

**Status: Pending. ~3-5 weeks estimated.**

**What it is:** One strategy at a time, paper-first then live, port MIDSEL (exit logic) and the arb scanner. Decide what to do with FADHYPE/NICHDOM (probably fold into data-svc's AI prompts rather than separate services). Permanently delete XMKTARB and LNGSHOT (dead code in the legacy bot — never resurrect).

**Why it exists:** Because TIMELY alone is one strategy. The legacy bot's profitability came from a few strategies cooperating. To match (and beat) the legacy bot, the rest of what worked needs to come along.

**Why it has to come after Phase 4:** TIMELY-live is the proof that the architecture handles real money correctly. Adding more strategies before that proof would be adding complexity to an unproven system.

**One at a time, not parallel:** If five strategies all go live the same day and the bot misbehaves, you don't know which strategy caused it. Sequential porting means each strategy's behavior is observable in isolation before the next one joins.

**What this enables:** The legacy bot can finally be retired. Phase 5 ends with a "shut it down for good" moment — a real milestone.

**v2 architecture reference:** Section 11 (Phase 5 description).

---

## Phase 6 — Hardening and MCP Integration

**Status: Pending. ~3-4 weeks estimated.**

**What it is:** Two things at once. (1) Make the system survive failure modes — kill ems-svc mid-fill, kill the database, kill NATS, write runbooks for each. (2) Build `mcp-svc`: an MCP server that exposes Midas to Claude as a first-class system. Read tools (what's the bot doing?), simulate tools (what would happen if?), write tools (pause, resume) with auth.

**Why it exists:** Because production systems aren't just "code that works on a sunny day." They're "code that works on a bad day too." Phase 6 stress-tests the system and writes the runbooks you'll need at 2am when something breaks.

**Why MCP integration here:** Because by Phase 6, the system is real and stable enough to safely expose. MCP integration gives you (and any future Claude) direct conversational access to the bot's state — "what positions do we have?" "pause TIMELY" "show me the last 10 bets."

**What this enables:** Confidence. Until Phase 6, the system works but you're not 100% sure what happens when things break. After Phase 6, you've broken every piece on purpose, watched it recover, and written down what to do.

**v2 architecture reference:** Sections 11 (Phase 6 description), 13 (MCP design).

---

## Phase 7 — Research and Growth (Ongoing, No End Date)

**Status: Pending. No fixed duration.**

**What it is:** Not a phase that ends — it's the mode the project enters once Phases 0-6 are done. Move shadow R&D content into experimental strategy services running in paper. Try Bayesian-Kelly sizing experiments. Add new data sources as MCPs. Add new strategies as new services.

**Why it exists:** Because a system you can't grow is a system that decays. Phase 7 is the mode where Midas earns its place by getting better over time.

**Why it has to come last:** Because experimentation requires a stable platform. You can't run controlled experiments on infrastructure that itself is changing. By Phase 7, the foundation is locked down — every experiment is "add a service, watch it for two weeks, decide" — never "rebuild the platform underneath."

**What this enables:** The whole point. A bot that gets smarter over years.

**v2 architecture reference:** Section 11 (Phase 7 description), Section 14 (research patterns).

---

## How to Read This During a Session

Before starting any Phase 1 task, ask: **"why does this exist in the journey, and what does it enable next?"**

If the answer is unclear, re-read this document. If the answer is *still* unclear, the task may not actually be needed — flag it as worth questioning, not worth doing on autopilot.

This is the antidote to the legacy bot's worst habit: **building things one at a time without a coherent plan**, until you ended up with 5,300 lines of `bot.py` where two strategies were dead code and nobody noticed for months.

Every commit lands on `main` because it serves the journey. If a commit doesn't serve the journey, it doesn't belong on `main`.

---

## Where We Are Right Now (May 6, 2026)

We are **mid-Phase 1**, at task 9.5 of 12 complete (~79%). The platform is almost wired. Specifically:

- **The platform's loading dock is built** (Argo CD, Task 6) — every future service deploys through it
- **The CI gate is live** (Task 4) — every commit gets tested before it can land
- **The data stores exist** (Postgres, Redis — Tasks 2, 3) — but no service is using them yet
- **The cluster is running** (Task 1) — three nodes in London, healthy
- **The locked supply room is built** (sealed-secrets, Task 7) — round-trip verified
- **Real credentials are sealed** (Task 8) — 4 SealedSecret files in `deploy/secrets/`, ready for services to mount
- **The kitchen intercom is running** (NATS JetStream, Task 9) — 3-replica cluster, durability proven
- **Half the observability stack is up** (Loki + Tempo, Task 10 partial) — logs and traces ready for Phase 2 services

What's missing before Phase 2 can start:
- **kube-prometheus-stack** (Task 10 finish) — metrics + alerting half of LGTM. Stuck on CRD bootstrap; Plan B documented. **Not a hard blocker** — Phase 2 can begin without it.
- **hello-svc proof-of-life** (Task 11) — the integration test that proves the whole stack works end-to-end. **This is the gate to Phase 2.**
- **Runbook** (Task 12) — operational documentation for the cluster.

Once hello-svc starts cleanly, Phase 1 closes and Phase 2 begins. Phase 2 = the first three real services from v2 §04 (data-svc, oms-svc, pms-svc). That's where Midas starts *looking like a bot* instead of *looking like infrastructure*.

**Cost so far:** ~$130/month
**Time invested so far:** ~16 hours across 4 sessions
**Calendar elapsed:** 7 days (April 29 → May 6)
**Remaining estimate:** 5-6 months for Phases 1-6, ongoing for Phase 7

**Latest commit on main:** `75aa2b8` — fix(deploy): add SkipDryRunOnMissingResource and Replace for kps

---

## Update Cadence

This document is updated:
- **At the end of every session** if anything we did changed our understanding of the journey
- **At the start of every new phase** to reflect what the previous phase actually delivered
- **Whenever a major architectural decision is made** that the architecture v2 doc doesn't cover

If this document gets stale (sessions go by without updating it), that's a signal that the project has lost connection to its own purpose. Reconnect before continuing.
