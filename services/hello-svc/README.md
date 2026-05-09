# hello-svc

Phase 1 proof-of-life service. Exercises the full Midas stack end-to-end:
Postgres (`SELECT 1`), Redis (`PING`), NATS (heartbeat publish every 60
seconds), and exposes `GET /health` for liveness checks.

Not a real trading-adjacent service. Will be deleted or repurposed when
Phase 2's `data-svc` / `oms-svc` / `pms-svc` replace it as the integration
target.
