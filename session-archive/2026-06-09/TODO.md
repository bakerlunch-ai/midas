# Midas — TODO

**Updated:** 2026-06-09 (end of session 10)
**HEAD:** `cd7c3d2` · 75 commits on main · 207 tests passing

---

## Right now — Next session opens here

**Top priority: get data-svc stable on the cluster.** The two-loop market selection architecture is shipped, tested, CI-verified, and deployed — but the deploy revealed three real-world calibration gaps. Address them in order, smallest fix first.

1. **Add startupProbe to data-svc deployment manifest** → v2 §03, §04
   - Liveness kills at ~70s; startup discovery takes ~103s against real Kalshi.
   - Fix: GitOps manifest change. `startupProbe: { httpGet: { path: /health, port: 8000 }, initialDelaySeconds: 0, periodSeconds: 10, failureThreshold: 30 }` (5 min grace).
   - No code change.

2. **Pin data-svc image by digest, not `:main` tag** → v2 §03
   - `kubectl rollout undo` is currently cosmetic because the deployment pins by mutable tag with `imagePullPolicy: Always`.
   - Fix: edit deploy manifest in git/Argo to pin by digest. Update via CI/CD on each release.

3. **Raise `max_pages` or paginate more selectively** → v2 §04
   - Kalshi has 20k+ open markets, front-loaded with illiquid sports parlays.
   - Our `max_pages=20` cap truncates BEFORE reaching liquid named-series.
   - Options: bump cap to 50/100; add server-side filter (if Kalshi supports query params); paginate by series.

4. **Tune liquidity thresholds from real data** → v2 §04
   - Default tier `min_volume_24h = 1000` is suspect; only 4 markets passed at startup, 0 on re-scan.
   - Env-var change only: `DATA_SVC_DEFAULT_MIN_VOLUME_24H`, `DATA_SVC_TIGHT_MIN_VOLUME_24H`, etc.
   - Watch discovery logs evolve.

5. **Investigate selected=4 (startup) vs selected=0 (loop re-scan) discrepancy** → v2 §04
   - Possible re-evaluation inconsistency or book-staleness mid-cursor-pagination.

---

## Phase status

| Phase | Goal | v2 ref | Status |
|---|---|---|---|
| 0 | Keep legacy stable | §01 | ✅ done |
| 1 | Cluster + data flowing | §03, §04, §05, §07 | 🔶 ~10/12 |
| 2 | OMS/PMS | §06, §07 | ⚪ pending |
| 3 | Risk service | §08 | ⚪ pending |
| 4 | Strategy framework | §09 | ⚪ pending |
| 5 | Websocket migration | §10 | ⚪ pending |
| 6 | First strategy on paper | §11 | ⚪ pending |
| 7 | Real money on first strategy | §12 | ⚪ pending |

---

## ⚪ Phase 1 — Cluster + data flowing → v2 §03, §04, §05, §07

### Done
- [x] DOKS cluster (do-lon1-midas-prod, 3 nodes) → v2 §03
- [x] Argo CD installed → v2 §03
- [x] NATS deployed → v2 §05
- [x] Postgres deployed → v2 §07
- [x] Redis deployed → v2 §07
- [x] hello-svc reference implementation → v2 §03
- [x] data-svc skeleton + Kalshi RSA auth → v2 §04
- [x] MarketTickEvent schema → v2 §05
- [x] NATS publisher → v2 §05
- [x] CI pipeline (lint + test) → v2 §02
- [x] iCloud .pth race fixed (session 10) → v2 §02
- [x] Two-loop market selection in code (session 10) → v2 §04
- [x] CI-verified bisectable commits (session 10) → v2 §02

### In progress / next
- [ ] **data-svc stable on cluster** → v2 §04
  - Add startupProbe (item 1 above)
  - Pin image by digest (item 2 above)
  - Tune scope + thresholds (items 3-5 above)
- [ ] Postgres event_envelope schema → v2 §07
- [ ] data-svc writes ticks to Postgres → v2 §04, §07

---

## ⚪ Phase 2 — OMS / PMS (pending) → v2 §06, §07

- [ ] event_envelope canonical schema (shared between PMS + OMS)
- [ ] PMS service skeleton
- [ ] PMS reads broker positions on startup
- [ ] PMS subscribes to OrderFilledEvent
- [ ] PMS reconciliation scheduler (binding constraint #2)
- [ ] OMS service skeleton
- [ ] OMS Kalshi order placement
- [ ] OMS order modification + cancel
- [ ] Cross-DB denial check (security)

---

## ⚪ Phase 3 — Risk service (pending) → v2 §08

- [ ] Risk service skeleton
- [ ] Exposure cap calculation
- [ ] Weekly loss limit
- [ ] Per-ticker max-entries
- [ ] Contradictory-position prevention
- [ ] Halt/allow decision event

---

## ⚪ Phases 4–7 — Strategies, websocket, paper, live → v2 §09, §10, §11, §12

(Detailed task lists land when we approach each phase.)

---

## Carry items (cross-cutting, no specific phase)

- [ ] GHA Node 20 deprecation — past June 2; warnings will harden into errors. Bump action versions.
- [ ] Harden CI alerting ("gate that watches the gate")
- [ ] kps + nats Argo OutOfSync — cosmetic DOKS quirks
- [ ] kube-state-metrics 0/1 — investigate
- [ ] Stale argocd-initial-admin-secret
- [ ] Postgres + Redis password rotation
- [ ] gh token read:packages scope
- [ ] tick_at → broker time (Phase 5 websocket)
- [ ] **DO API token expires ~July 27, 2026 — remind ~July 20**
- [ ] Tier-2 CI enhancements (mypy, coverage, container scanning) — defer to Phase 3
- [ ] Move repo out of `~/Desktop` in future (iCloud hygiene)
- [ ] docs/ARCHITECTURE.md stub

---

## Patterns / agreements added this session

1. **Fix-it bias.** When the fix is small and the gap is named, fix it. Don't carry inefficiencies.
2. **Independent CI per commit.** If a commit lands in a push-pair and we want bisectability, push it as its own branch tip first (`git push origin SHA:refs/heads/temp-branch`, watch CI, delete).
3. **A green rollback message is not a real rollback.** Verify digest, verify image, verify behavior — `kubectl rollout undo` on a mutable-tag deployment is cosmetic.
4. **Switch-and-restore for bakerlunch-ai push.** `gh auth switch -u bakerlunch-ai && gh auth setup-git && git push && gh auth switch -u Pippo-min`. Used 3x this session, clean each time.

---

## What "done" looks like for Phase 1

- data-svc pod stable on cluster, no liveness restarts across multiple discovery cycles
- Discovery logs show `selected=N` where N is in the dozens-to-low-hundreds, with a healthy series breakdown (KXFED=X KXPRES=Y …)
- Tick poll logs show `published>0` consistently
- MarketTickEvents flowing through NATS (verify with a debug subscriber)
- Postgres event_envelope schema landed, data-svc writes ticks
- All thresholds calibrated from real logs (no more env-var tweaks needed for steady-state)

When all of those are true, Phase 1 closes and Phase 2 (OMS/PMS) opens.
