# Lessons from the old bot

This document is the explicit list of mistakes the previous Kalshi bot made, and the patterns Midas commits to not repeating. It exists because every one of these mistakes felt reasonable at the time it was made. Without writing them down, we will make them again.

Read this at the start of every working session. When you are about to take a shortcut, check if it appears below.

---

## 1. Bankroll only goes up

**What happened:** the old bot stored `bankroll_pool` as a single mutable field. Code paths existed to increment it (deposits, wins) but no code path ever decremented it. Losses were recorded in a separate log but never flowed back to the bankroll number. The bot's internal view of its own balance drifted upward over weeks until it was wildly out of sync with Kalshi reality.

**The lesson:** never store balances or positions as mutable fields. State that changes is event-sourced. Bankroll is not a number — it is the result of replaying every deposit, every withdrawal, every win, every loss.

**In Midas:** `pms-svc` uses an append-only PostgreSQL event log. Bankroll is computed by summing event deltas. There is no "decrement" code path because there is no stored balance to decrement.

---

## 2. Reconciliation never ran

**What happened:** the old bot had a function called `reconcile_with_kalshi`. It was written, committed, and never wired into a scheduler. It ran exactly once in months — manually, days before an audit. The bot's internal state and Kalshi's reality silently diverged the entire time.

**The lesson:** if a function is critical to correctness, it must be on a schedule and its output must be observable. A reconciliation function that no one runs is the same as no reconciliation function.

**In Midas:** OMS and PMS both run reconciliation jobs daily, automatically. Drift events are published to NATS and trigger Telegram alerts. The reconciliation status is a Grafana metric we watch.

---

## 3. Strategies as strings, not enforced types

**What happened:** the old bot tracked which strategy placed each bet via a string field called `strategy_triggered`. The string was set wherever the bet was created. There was no enforcement that the string was correct, non-empty, or even one of the known strategies. By the time of the audit, 77 of the bot's bets had `strategy_triggered = "unknown-reconciled"` because somewhere along the way the string had been lost.

**The lesson:** if a value is critical (and strategy attribution is critical for performance analysis), the type system must enforce it. Strings are too loose.

**In Midas:** `BaseEvent` requires every subclass to declare `event_type` and `event_version` as `ClassVar[str]`. `__init_subclass__` raises `TypeError` at class-definition time if either is empty. You cannot define a malformed event subclass — Python will refuse to load the code.

---

## 4. Eight strategies, two of which were dead code

**What happened:** the old bot's documentation listed eight strategies. The audit found that two of them (XMKTARB, LNGSHOT) had been written, committed, and never wired into the scheduler. They were defined but never invoked. Nobody noticed for months because there was no "what is actually running" view.

**The lesson:** the documented system and the running system must match. If something exists in code but doesn't run, it is dead code and must be deleted, not kept "in case we need it later."

**In Midas:** every strategy is its own service deployed via Argo CD. If a strategy is not deployed, it is not in the running system. The Grafana dashboard shows which strategies are emitting heartbeats. Dead strategies are visible immediately.

---

## 5. Risk gates duplicated in eight places

**What happened:** the old bot had seven risk checks (status, weekly loss, exposure cap, contradictory positions, ticker concentration, etc.) implemented in `_place_auto_bet`. Three of those checks were also implemented elsewhere — in TIMELY's scan loop, in arb scanner, in `_check_sufficient_balance`. When we wanted to change a threshold, we changed it in one place and the others silently used the old value.

**The lesson:** business logic that protects the firm goes in exactly one place. Other places call into it. If a rule is enforced in two places, it will diverge.

**In Midas:** all risk gates live in `risk-svc`. Strategies do not enforce risk; they propose orders. Risk-svc is the only thing that approves or rejects. There is exactly one implementation of the weekly loss limit, the exposure cap, etc.

---

## 6. Shadow bot drifted into a research lab

**What happened:** `shadow_bot.py` was meant to be a paper-trading mirror of the real bot. Over time it accumulated multi-model AI consensus, Manifold/Metaculus integration, news sentiment, ten "risk extensions," and a dead Polymarket scanner. None of those features were promoted to the real bot. None of them produced reports anyone read. Shadow became 60% larger than the real bot, did completely different things, and was unable to answer the question "would this strategy have worked in production?"

**The lesson:** paper trading and research are different concerns and must not share a process. A paper environment must run the same code as live, with simulated execution. Research belongs in experimental services or notebooks, clearly labeled as such.

**In Midas:** the `trading-paper` Kubernetes namespace runs the same images as `trading-prod`. The only difference is configuration — paper EMS simulates fills instead of placing real orders. Experimental ideas become experimental strategy services in paper, separate from the proven strategies, with their own metrics. Research happens in Jupyter notebooks reading the event log.

---

## 7. The state file was 34 keys deep with no schema

**What happened:** `betting_state.json` accumulated 34 distinct keys over the bot's lifetime. Some keys were read by code; some were written but never read; some were read but never written. There was no schema. There was no way to know which keys were live versus legacy. The phantom-read at line 2712 (reading a `streaks` key while the data lived in `category_streaks`) is one example among many.

**The lesson:** state must have a schema. Schema must be enforced. Adding a field is a schema change, not a casual edit. Removing a field is a deliberate process.

**In Midas:** every event has a JSON Schema. Pydantic enforces it at construction time. Schemas are versioned. Adding a required field requires a version bump. Removing a field is forbidden — only deprecation is allowed. Old consumers continue to work.

---

## 8. The learning system never learned

**What happened:** the old bot maintained a `learning_log` — a 500-entry rolling buffer of recent outcomes, intended to feed back into strategy weights and confidence multipliers. The audit found that the buffer was written by the resolution handler but never read by anything. The actual "learning" came from `_compute_performance_stats` which recomputed multipliers directly from the bets list every time it was called. The `learning_log` was dead writes.

**The lesson:** if data is written but never read, it is technical debt with no upside. Every piece of state must have a reader. If the reader doesn't exist yet, the state shouldn't exist yet.

**In Midas:** events flow through NATS. Subscribers are explicit. If no service subscribes to an event type, it is not emitted. Dead writes are visible (NATS shows them as messages with zero consumers) and removed.

---

## 9. Magic numbers everywhere, no config layer

**What happened:** the old bot had thresholds hardcoded throughout the codebase. The half-Kelly multiplier was `0.5` in three different files. The TIMELY price band was `(0.18, 0.30)` typed directly into the scan loop. Adjusting any parameter required code changes, code review, and redeployment.

**The lesson:** parameters that may be tuned belong in config, not in code. Code expresses logic; config expresses policy. They live in different files, change for different reasons, and have different review processes.

**In Midas:** all tunable parameters live in YAML configuration loaded at service startup. Strategies declare their tunables. Risk thresholds live in `risk-svc` config. A parameter change is a config PR, not a code change. The list of tunables is itself part of the service contract.

---

## 10. The bot grew faster than its tests

**What happened:** the old bot reached 5,317 lines in `bot.py` with virtually no test coverage. New strategies were added by editing the giant file and shipping. Bugs were caught in production, sometimes after they had cost money. The team did not trust changes because there was no way to verify behavior except by running the bot live.

**The lesson:** tests are not optional and they are not a phase that comes later. Every meaningful piece of logic is tested before it is deployed. CI fails the build if tests fail. The cost of writing tests is paid back many times in faster, safer changes.

**In Midas:** every service has unit tests. The shared `bot-events` package already has 5 tests for `BaseEvent` alone. CI runs `make lint` and `make test` on every PR. No code merges to main with failing checks. No service deploys with skipped tests.

---

## The meta-lesson

Every entry above started as a small, reasonable decision. None of them were laziness. They were all "we'll fix it later" or "this is fine for now" or "we don't have time to do it properly." Multiplied across months, they produced a system that was technically working but practically untrustworthy.

The price of doing things properly is paid in small amounts over time. The price of not doing them is paid in audit findings, bugs that lose real money, and rebuilds.

Midas exists because the price of the second option turned out to be higher than we expected. We will not pay it again.
