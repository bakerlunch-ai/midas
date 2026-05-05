# deploy/

Kubernetes manifests for Midas services. Deployed via Argo CD (Phase 1 Task 6+). Subdirectories per service or per environment to be decided as services land.

The decision to keep manifests in-tree (rather than in a separate `midas-deploy` repo) is recorded in `docs/PHASE_1_PLAN.md` Task 5. Re-evaluate if the team grows, an ops/eng permission boundary is needed, or running CI on every infra commit becomes annoying.
