# Midas — Session History

Append-only log. Newest at top. Never delete or edit prior rows.

---

## Sessions

| # | Date | Duration | What shipped | Commits | Phase milestone | Report |
|---|---|---|---|---|---|---|
| 10 | 2026-06-09 | ~3h | Two-loop market selection (discovery + tick), iCloud .pth race fix, both Commit A + B independently CI-verified. Deployed to cluster (revealed real-Kalshi calibration gaps: startupProbe needed, max_pages too tight). | +4 (71 → 75) | Phase 1: ~9/12 → ~10/12 | [SESSION_REPORT_2026-06-09.html](session-archive/2026-06-09/SESSION_REPORT_2026-06-09.html) |
| 9 | 2026-05-28 | ~2h | PR 1 landed (KalshiClient pagination); PR 2 outlined (market selector with allowlist + liquidity labeling); CI working-agreement #9 added ("a green Build is not a green CI"). | +N | Phase 1 (data-svc selection design locked) | (archive) |
| 8 | 2026-05-?? | — | Field-mapping bug fix in data-svc; test-first discipline locked. | +N | Phase 1 | (archive) |
| 7 | 2026-05-?? | — | data-svc skeleton + Kalshi RSA auth verified live in cluster. | +N | Phase 1 | (archive) |
| 6 | 2026-05-06 | — | data-svc deployed to cluster for first time. | +N | Phase 1 | (archive) |
| 5 | 2026-05-?? | — | MarketTickEvent schema + NATS publisher. | +N | Phase 1 | (archive) |
| 4 | 2026-05-04 | — | hello-svc reference implementation, NATS/Postgres/Redis deployed. | +N | Phase 1 | (archive) |
| 3 | 2026-04-?? | — | Argo CD installed; first hello-world deploy. | +N | Phase 1 | (archive) |
| 2 | 2026-04-?? | — | DOKS cluster provisioned (do-lon1-midas-prod, 3 nodes). | +N | Phase 1 start | (archive) |
| 1 | 2026-04-29 | — | Repo bootstrapped (`bakerlunch-ai/midas`), v2 architecture document locked. | +N | Phase 0 → Phase 1 | (archive) |

---

## Cumulative metrics over time

| As of session | Phases done | Total cost/mo | Commits on main | Services running | Tests | Notes |
|---|---|---|---|---|---|---|
| 10 (2026-06-09) | 0 (Phase 1 ~10/12) | ~$130 | 75 | data-svc (flaky), hello-svc, NATS, Postgres, Redis, Argo, kps | 207 pass | Two-loop selection shipped; cluster needs startupProbe |
| 9 (2026-05-28) | 0 (Phase 1 ~9/12) | ~$130 | 71 | data-svc, hello-svc, NATS, Postgres, Redis, Argo | 161 pass | Pagination shipped; selection design locked but not implemented |
| 8 | 0 | ~$130 | ~65 | (same) | ~150 pass | Field-mapping fix |
| 6 (2026-05-06) | 0 | ~$130 | ~50 | data-svc deployed first time | ~120 pass | Cluster verified live |
| 4 (2026-05-04) | 0 | ~$130 | ~30 | hello-svc, NATS, PG, Redis | ~60 pass | Infrastructure base |
| 1 (2026-04-29) | 0 | $0 | 1 (initial) | none | 0 | Repo bootstrap |

---

## Session 10 details (2026-06-09)

**Theme:** Two-loop market selection — designed, implemented, shipped, deployed.

**Bookend state:**
- Start: HEAD `a28104f`, 161 tests, data-svc publishing 0 markets in tight loop
- End: HEAD `cd7c3d2`, 207 tests, data-svc on new image flaky-but-up

**Commits pushed (4):**
- `cd93039` — fix(tests): pytest pythonpath survives iCloud-hidden .pth
- `b10b572` — build(make): _unhide-pth fail loud + iCloud cause
- `6fddec5` — feat(data-svc): market selection rules + Kalshi pagination
- `cd7c3d2` — feat(data-svc): wire two-loop market selection

**Working agreements added:**
1. Fix-it bias (don't carry small named inefficiencies)
2. Independent CI per commit (push as temp branch tip when needed)
3. "Green rollback message ≠ real rollback" (verify behavior, not exit codes)

**Real-data calibration gaps surfaced (carry):**
1. data-svc startup ~103s on real Kalshi (20k markets) vs liveness probe killing at ~70s — no startupProbe
2. `:main` tag + `imagePullPolicy: Always` means `kubectl rollout undo` is cosmetic
3. `max_pages=20` truncates 20k front-loaded sports parlays before reaching liquid named-series

**Filippo pushed back twice on Claude's "leave it" instinct, correctly both times.** Calibration adjusted in the working agreement.
