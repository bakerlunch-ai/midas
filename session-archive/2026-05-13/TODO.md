# Midas — Living TODO

> **Updated:** May 13, 2026 (end of session 7)
> **Format:** Living checklist. Updated at end of every session.
> **Aligned with:**
> - The big picture → `Bot_Architecture_v2_Professional_Grade_April26_2026.html` Section 11 (8-phase migration roadmap)
> - Phase progress narrative → `docs/JOURNEY.md`
> **Pair this with:** `docs/PROJECT_HANDOFF.html` (current state) and `docs/SESSION_HISTORY.md` (chronological log)

---

## 🎯 Right now — Next session opens here

- [ ] **data-svc piece #7: sealed-secret for Kalshi credentials.** Install `kubeseal` CLI. Fetch cluster's sealing public cert. Pull real `KALSHI_API_KEY_ID` + `KALSHI_PRIVATE_KEY_PEM` from legacy bot's `.env` on the NAS. Encrypt → commit to `deploy/secrets/data-svc/kalshi-credentials.yaml`. ~30-45 min. → v2 §05, §09
- [ ] **data-svc piece #8: Argo Application + deploy + verify.** Write `deploy/applications/data-svc.yaml`. Push. Watch Argo through app-of-apps. Watch pod come up. See ticks in Loki. Confirm a NATS subscriber sees `events.market.tick.kalshi.*` messages. ~30-60 min depending on DOKS. → v2 §05, §07, §09
- [ ] **Optional (carry items, only if DOKS apiserver healthy):** File DigitalOcean support ticket about openapi-flake (evidence captured session 7); investigate nats StatefulSet drift with helm template diff.

---

## 📊 Phase status at a glance

| Phase | Description | v2 ref | Duration estimate | Status |
|---|---|---|---|---|
| **Phase 0** | Keep the lights on (old bot paused) | §11 P0 | ongoing | ✅ Active |
| **Phase 1** | Infrastructure foundation | §05–§10 | 2-4 weeks | ✅ **DONE (12/12, closed session 6)** |
| **Phase 1.5** | Architectural cleanup (discovered session 6) | §08, §09 | 1 session | ✅ **3/3 closed (9 minor carry items)** |
| **Phase 2** | Core data layer (data, oms, pms services) | §02, §03, §04, §06 | 3-4 weeks | 🟡 **In progress** (vocab 7/7, data-svc 6/8 pieces, oms/pms 0/2) |
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

## ✅ Phase 1 — Infrastructure foundation (12/12 DONE) → v2 §05–§10

> All 12 tasks complete as of end of session 6. The cluster has everything a real service would need: cluster, DBs, message bus, observability, GitOps, sealed-secrets, CI/CD, and a smoke service that proved it all wired together correctly.

- [x] Task 1 — Kubernetes cluster → v2 §05
- [x] Task 2 — Managed PostgreSQL → v2 §06 _(cross-DB denial check deferred to Phase 2)_
- [x] Task 3 — Managed Redis → v2 §06
- [x] Task 4 — GitHub Actions CI → v2 §10
- [x] Task 5 — Decided on in-tree manifests → v2 §09
- [x] Task 6 — Argo CD installed → v2 §09
- [x] Task 7 — Sealed-secrets controller → v2 §09
- [x] Task 8 — Credentials in sealed-secrets → v2 §09
- [x] Task 9 — NATS JetStream → v2 §07
- [x] Task 10 — LGTM observability stack → v2 §08 _(verified end-to-end in session 6 after Phase 1.5 fixes)_
- [x] Task 11 — Hello-world end-to-end deploy → v2 §02, §05–§10
- [x] **Task 12 — Operations runbook (session 6)** → v2 §10, §14 _(commit `febf24e`)_

---

## ✅ Phase 1.5 — Architectural cleanup (3/3 DONE, session 6) → v2 §08, §09

> Discovered while verifying Phase 1 Task 10. Three architectural problems that were invisible from Argo's "Synced+Healthy" status because Argo's "Synced" only means "cluster matches last applied," not "cluster matches git" and not "system actually does its job."

### ✅ Problem 1 — App-of-apps (DONE, biggest architectural win of the night) → v2 §09

- [x] `deploy/applications/app-of-apps.yaml` created; one Argo Application watching the whole folder, manages itself recursively (commit `d394254`)
- [x] Bootstrap-applied once via `kubectl apply`; self-sustaining from then on
- [x] selfHeal + prune both enabled; ServerSideApply=true
- [x] Synced + Healthy on first poll
- [x] Pattern proven end-to-end three times tonight via subsequent alloy.yaml edits

### ✅ Problem 2 — Log shipper (DONE, three iterations) → v2 §08

- [x] **v1** (commit `8e192c7`) — Alloy DaemonSet, K8s-API-based. First GitOps end-to-end deploy. CRUSHED single-binary Loki by backfilling 3+ days of pod logs from epoch.
- [x] Bleed stopped — DaemonSet scaled to 0 via `nodeSelector: midas/disabled=true` trick. Loki recovered in <30s.
- [x] **v2** (commit `7216a72`) — Switched to file-based collection. Web search confirmed `tail_from_end` not supported on `loki.source.kubernetes` (grafana/alloy#3550). Used `local.file_match` + `loki.source.file` with `tail_from_end = true` reading from `/var/log/pods/*`.
- [x] **v3** (commit `6d25248`) — Added drop relabel rule for kube-system + monitoring namespaces (DOKS chatter + observability self-logs that would saturate single-binary Loki). Verified with `count_over_time` instant queries: kube-system 0 lines/2min, monitoring 0, hello-svc 16 (matches 10s health-probe rate), argocd 130. Loki /ready stable.
- [x] 3 Alloy pods 2/2 Running on grafana/alloy:v1.4.3

### ✅ Problem 3 — Grafana datasources (DONE) → v2 §08

- [x] Added `grafana.additionalDataSources` block to `deploy/applications/kube-prometheus-stack.yaml` (commit `c04eed4`)
- [x] Argo sync EOF'd mid-patch on ClusterRole/admission. Bypassed by direct ConfigMap patch on `kps-kube-prometheus-stack-grafana-datasource` with same content.
- [x] Grafana kiwigrid sidecar auto-reloaded within ~30s. All 4 datasources confirmed via Grafana API: Alertmanager, Loki, Prometheus, Tempo.

### 🚧 Phase 1.5 carry items (open after session 7) — DO NOT FORGET

| Item | Status | Disposition |
|---|---|---|
| `kube-prometheus-stack` Argo Application stuck OutOfSync | Open | Functional fix already live in cluster (direct ConfigMap patch). Argo bookkeeping won't reconcile — operation started 01:46:51Z and never finished due to apiserver EOF on ClusterRole patch. Two cancel-and-retry attempts tonight failed (second trigger swallowed). Retry once DOKS stabilizes for sustained window, OR add `SkipPreSyncCheck=true` to syncOptions, OR delete the stuck PreSync hook resources manually and let Argo recreate. Evidence at `/tmp/kps-stuck-evidence.txt`. |
| `nats` Argo Application OutOfSync | Open (pre-existing) | Cosmetic. NATS itself fine (3 pods 2/2 Running 5+ days). `kubectl diff` to identify drift, reconcile in git or cluster. ~10 min. |
| DigitalOcean apiserver instability | External (not ours) | 4+ EOF incidents tonight, one ~25-min sustained outage. kube-state-metrics restart count grew 28 → 47 (+19) over session. File DO support ticket with evidence. |
| Postgres oms_user + Redis default password rotation | Open (from May 9) | Both creds leaked in chat May 9 via `kubectl get secret -o jsonpath='{.data}'`. VPC-only access mitigates external risk. Rotate when convenient. |
| Redis security patch | Open | DigitalOcean flagged available patch on managed Redis. Apply in maintenance window. |

---

## 🟡 Phase 2 — Core data layer (vocab 7/7, data-svc 6/8 pieces) → v2 §02, §03, §04, §06

> Goal: the data backbone works. The system ingests market data, has working event-sourced ledgers, is fully observable.

### ✅ bot-events vocabulary (DONE, session 6) → v2 §04

| Commit | Event | Subject | Tests |
|---|---|---|---|
| `e5b816d` | MarketTickEvent | `events.market.tick.<exchange>.<ticker>` | 12 |
| `ded54ee` | OrderPlacedEvent | `events.order.placed.<exchange>.<ticker>` | 17 |
| `d90575e` | OrderFilledEvent | `events.order.filled.<exchange>.<ticker>` | 16 |
| `50b7225` | OrderCancelledEvent | `events.order.cancelled.<exchange>.<ticker>` | 13 |
| `25c6ba7` | PositionOpenedEvent | `events.position.opened.<exchange>.<ticker>` | 16 |
| `cf4ccc1` | PositionClosedEvent | `events.position.closed.<exchange>.<ticker>` | 18 |
| `d23d13f` | BankrollChangedEvent | `events.bankroll.changed` | 16 |

bot-events package: 9 types (Base + Heartbeat + 7 new), 120 passing tests. Event-sourcing discipline encoded: order-level facts on OrderPlacedEvent only (joined via exchange_order_id); bankroll = sum of deltas (binding constraint #1); realized P&L pre-computed on PositionClosedEvent (canonical source: pms-svc); Decimal everywhere, no floats.

### 🟡 Services to build — data-svc 6/8 pieces done

**data-svc — Kalshi adapter (market data ingest). Emits `MarketTickEvent` on `events.market.tick.<exchange>.<ticker>`. → v2 §02, §05**

| Piece | Description | Status |
|---|---|---|
| 1 | Workspace scaffold + read-only `KalshiClient` + 11 tests | ✅ commit `51e52a2` (session 6) |
| 2 | FastAPI `main.py` with lifespan-managed KalshiClient + fail-loud auth probe | ✅ commit `07aa840` (session 7) |
| 3 | `NATSPublisher` + lifespan wiring with fail-loud NATS connect probe | ✅ commit `eb43e3c` (session 7) |
| 4 | **Tick poller** — first service that actively emits events. Defensive parser; empty-book markets skipped, never zero-emitted. | ✅ commit `b821e83` (session 7) |
| 5 | Dockerfile + GitHub Actions build pipeline → image in GHCR on every push | ✅ commit `7b6cbc9` (session 7) |
| 6 | K8s manifests (Deployment, Service, Namespace) — references not-yet-existing `kalshi-credentials` sealed-secret | ✅ commit `a6ec221` (session 7) |
| 7 | **NEXT:** Sealed-secret for Kalshi credentials | ⏳ next session |
| 8 | Argo Application + deploy + verify ticks flowing on NATS | ⏳ next session |

**oms-svc — event-sourced order log against `oms_db`. Emits OrderPlaced/Filled/Cancelled. → v2 §02, §03**
- [ ] Not started. Will follow data-svc's canonical shape (lifespan-managed connections, fail-loud probes, defensive parsing).

**pms-svc — event-sourced portfolio log against `pms_db`. Emits PositionOpened/Closed and BankrollChanged. → v2 §02, §03**
- [ ] Not started. Same canonical shape as data-svc and oms-svc.

### ⚪ Integration checkpoints

- [ ] Deploy data-svc end-to-end (pieces 7 + 8 next session)
- [ ] Verify ticks visible in Grafana Loki by `{namespace="data-svc"}` query
- [ ] Verify ticks consumable on NATS subject `events.market.tick.kalshi.*` via a test subscriber
- [ ] Deploy oms-svc + pms-svc to the same `trading-paper` namespace
- [ ] Verify event-sourcing: manually inject a deposit event, verify bankroll projection updates
- [ ] Wire reconciliation jobs to scheduler (binding constraint #2)
- [ ] **Execute the cross-DB denial check** (oms_user → pms_db should fail) — carried over from Phase 1 Task 2

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
| **Phase 1.5 — kps Argo OutOfSync** | Re-diagnosed session 7: NOT a stuck PreSync hook — DOKS apiserver `/openapi/v2` 32s read drops mid-stream. `retryCount: 5/5` exhausted. Functional fix already live in cluster. | Retry on green apiserver day, or `SkipPreSyncCheck=true` syncOption |
| **Phase 1.5 — nats Argo OutOfSync** | Re-diagnosed session 7: real drift on `apps/StatefulSet nats/nats` — ServerSideApply silently skips immutable field (likely `volumeClaimTemplates`). NATS pods 0 restarts 6+ days. | Identify field via `helm template` diff or `argocd app diff`; then `ignoreDifferences` patch OR `--cascade=orphan` recreate |
| **Phase 1.5 — DigitalOcean apiserver instability** | 4+ EOFs in session 6; kube-state-metrics restarts 28→47. Affects every kubectl write. | File DO support ticket with `/tmp/kps-stuck-evidence.txt` evidence |
| **Phase 1.5 — Postgres oms_user + Redis password rotation** | Leaked in chat May 9; VPC-only mitigates external exposure | Rotate when convenient |
| **Phase 1.5 — Redis security patch** | DO flagged available patch | Apply in maintenance window |
| **Cross-DB denial check** (oms_user → pms_db) | Verifies Postgres role isolation | Phase 2 (when wiring service permissions) |
| **Local gh token missing read:packages/write:packages** | Can't list GHCR packages from CLI; browser works; CI unaffected | Optional, fix if doing manual GHCR debugging |
| **`/health` is dumb liveness only** | Currently returns `{ok:true}` regardless of dependency state | Split into `/health` (process up) + `/ready` (deps healthy) before first real strategy ships |
| **`nc.close()` vs `nc.drain()` in lifespan teardown** | Fine for fire-and-forget heartbeats. Drain matters when pending replies need to flush | Revisit when first request/reply consumer ships |
| **`imagePullPolicy: Always` + mutable `:main` tag** | Argo CD sees no diff when image content changes; no rollback by tag | Switch to per-SHA pinning before first real strategy ships |
| **Container name `app` (not service name)** | Avoids `kubectl logs hello-svc -c hello-svc` collision | Keep as convention for all future services |
| **GHA actions on Node.js 20** | GitHub forces Node 24 default Jun 2 2026, removes Node 20 Sep 16 2026 | Bump action pins when v5/v7+ Node-24 versions ship |
| **DO droplet limit at 3 (currently capped)** | Cluster is 3 nodes, at cap | Request bump before scaling cluster |
| **DO account status "warning"** | `doctl account get` shows Status: warning. Reason unknown. | Investigate in DO console |
| **DigitalOcean API token expires ~July 27, 2026** | If expired, doctl stops working | Calendar reminder for ~July 20, 2026 |
| **Bot-events consumers each need own paths in build workflow** | Phase 2's data-svc/oms-svc/pms-svc each need `build-<svc>.yml` | When building each new service (data-svc done session 7) |
| **kube-state-metrics 0/1 Ready** _(new session 7)_ | 50 restarts in past apiserver-flake window. Last restart 9h ago, currently quiet but not ready. | Investigate current container live logs; low priority |
| **Stale `argocd-initial-admin-secret`** _(new session 7)_ | Admin password rotated; initial-admin-secret no longer authenticates. Cosmetic but misleading. | `kubectl delete secret argocd-initial-admin-secret -n argocd`. Add rotation note to RUNBOOK. |
| **`gh` token lacks `read:packages` scope** _(new session 7)_ | Can't verify GHCR image tags via API. Build-and-push step success is current proxy. | One-time: `gh auth refresh -h github.com -s read:packages` |
| **tick_at uses `datetime.now(UTC)` not broker time** _(new session 7)_ | Kalshi `/markets` endpoint has no per-market timestamp. Schema docstring updated to acknowledge v1 reality. | Phase 5: when migrating to Kalshi websocket, replace with broker-side time |
| **Kalshi field names unverified** _(new session 7)_ | `no_bid`, `no_ask`, `open_interest`, `last_price` field names inferred from docs, not confirmed against legacy bot code. | First deploy validates — defensive parser logs and skips per-market on ValidationError |

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
9. **Always check `/mnt/project/` for prior artifacts before generating session-close docs.** Patterns established in prior sessions live in those files. Read first, then update — do not regenerate from scratch.

---

## 📊 By the numbers (current)

- **Commits on main:** 61 (53 → 61, +8 in session 7)
- **Latest commit:** `a6ec221` deploy(data-svc): add K8s manifests (Deployment, Service, Namespace)
- **Current phase:** Phase 2 (core data layer — data-svc actively under build)
- **Phase 1 progress:** ✅ **12 / 12 tasks complete (closed end of session 6)**
- **Phase 1.5 progress:** ✅ **3 / 3 architectural problems closed; 9 minor carry items**
- **Phase 2 progress:** Event vocabulary **7/7**; data-svc **6/8 build-pieces**; oms-svc + pms-svc **0/2 not started**
- **Overall progress:** Phase 1 done, Phase 2 partial. First service in cluster expected next session.
- **Cloud cost:** ~$130 / month (target: <$150)
- **Quality gates:** 3 / 3 passing (install, lint, test)
- **Tests:** 156 passing (141 → 156 in session 7, +15)
- **Services running:** hello-svc + full Phase 1 infrastructure. data-svc image **in GHCR**, manifests in git, pod **not yet deployed** (pieces 7+8 pending).
- **Argo Applications:** 9 total (7 Synced+Healthy, 2 OutOfSync but cosmetic; data-svc Application file not yet committed)
- **Last session:** May 13, 2026 (~6-7h, 8 commits — most productive Midas session by commits + Phase 2 progress)
- **Session 7 milestone:** First service that actively generates events (tick poller, commit `b821e83`). Two commits away from being live in cluster.
