# Phase 1 Plan — Infrastructure Foundation

Goal: stand up the cloud infrastructure that all eight Midas services will run on. End state: an empty Kubernetes cluster with NATS, Postgres, Redis, and the LGTM observability stack running, fully observable from a Grafana dashboard, deployable via GitOps. No trading services yet — that's Phase 2.

Estimated effort: 2-4 weeks of evening/weekend work. Estimated cost: ~$100-150/month ongoing once complete.

Read `docs/LESSONS_FROM_OLD_BOT.md` before starting. Do not skip the verification step on any task.

---

## Tasks in order

### 1. Provision the Kubernetes cluster

**What:** create a DigitalOcean Kubernetes (DOKS) cluster in a UK or EU region. 3 small worker nodes. Free managed control plane.

**Done when:**
- `kubectl get nodes` from your laptop returns 3 Ready nodes
- kubeconfig is saved at `~/.kube/config-midas` and selected via `KUBECONFIG` env var
- Cluster cost is visible in DigitalOcean billing dashboard (sanity check)

**Notes:** done manually in the DigitalOcean web UI, not through Claude Code. Claude Code does not have permission to spend money. Peter clicks the buttons.

**doctl gotcha:** `doctl` 1.155+ removed the `--kubeconfig` flag on `doctl kubernetes cluster kubeconfig save`. To write into a dedicated file (rather than merging into `~/.kube/config`), set the env var on the call itself:

```
KUBECONFIG=~/.kube/config-midas doctl kubernetes cluster kubeconfig save midas-prod
```

If the file does not yet exist, doctl will create it. The context name inside the file will be `do-lon1-midas-prod`.

**Repo-move gotcha:** if the Midas repo is moved to a different folder (e.g. `~/midas` → `~/Desktop/midas`), the uv `.venv` will appear to still work but `uv run` will fail with `Failed to spawn` errors. This is because virtual envs hardcode absolute paths in their script shebangs and `pyvenv.cfg`. Rebuild with `rm -rf .venv && make install` after any move.

---

### 2. Provision managed PostgreSQL

**What:** create a DigitalOcean managed PostgreSQL instance, smallest tier (1GB RAM, 10GB storage). Same region as the cluster. Three logical databases inside it: `oms_db`, `pms_db`, `reporting_db`. Three database users, one per logical DB, with access only to their own DB.

**Done when:**
- `psql` from your laptop can connect to all three databases
- Each user can only see their own database (verified by attempting cross-DB access and getting denied)
- Connection strings are saved (we'll put them in sealed-secrets in a later task)

**Status (2026-04-29):** proof-of-life done with `oms_user` only — a one-shot pod inside `midas-prod` connected to `oms_db` over the VPC private host on port 25060 and ran a `SELECT`. Cross-DB denial check and the remaining user verifications (`pms_user`/`pms_db`, `reporting_user`/`reporting_db`) are deferred to Phase 2, when we wire up per-service permissions and can validate them as part of the service contract rather than a one-off probe.

---

### 3. Provision managed Redis

**What:** create a DigitalOcean managed Redis instance, smallest tier (1GB). Same region.

**Done when:**
- `redis-cli` from your laptop can connect with TLS
- Connection string is saved

**Status (2026-05-04): DONE.**

- Cluster name: `midas-redis`, region LON1, Valkey 8
- Plan: Basic Regular SSD, 1GB RAM / 1 vCPU / 10 GiB, $15/mo
- Cluster UUID: `8671e021-fe36-4354-915b-731be8dc9602`
- VPC private host pattern: `private-midas-redis-do-user-36599881-0.e.db.ondigitalocean.com`
- Port: `25061`, TLS required, username: `default`
- Network locked: only trusted source is the `midas-prod` Kubernetes cluster
- Proof-of-life verified: an ephemeral pod inside `midas-prod` ran `redis-cli ... ping` and got `PONG`
- Password reset twice during the session (leaked into chat both times by accident — currently safe in Filippo's password manager)
- Gotcha: `doctl databases user reset` requires the **cluster UUID**, not the cluster name; the name returns 404

---

### 4. Set up GitHub Actions CI for the repo

**What:** add a workflow file `.github/workflows/ci.yml` that runs `make install`, `make lint`, `make test` on every PR and every push to main. CI must pass before merge.

**Done when:**
- A test PR is opened with a deliberately broken test; CI fails; PR is blocked from merging
- The PR is fixed; CI passes; merge button becomes available
- Branch protection rules on `main` require CI to pass before merge

**Status (2026-05-04): DONE (with one carve-out — see below).**

- `.github/workflows/ci.yml` runs `make install` / `make lint` / `make test` on every push and on PRs targeting `main`. Pinned action versions: `actions/checkout@v4`, `actions/setup-python@v5`, `astral-sh/setup-uv@v3`, `actions/upload-artifact@v4`. uv cache is keyed by `uv.lock` hash. Pytest output is uploaded as an artifact on failure for debugging.
- Closes lesson #10 from `docs/LESSONS_FROM_OLD_BOT.md` ("the bot grew faster than its tests"). CI now gates every change.
- **Branch protection deferred.** GitHub requires the Team plan ($16/mo) to enforce branch protection rules on private repos. Decision: stay on the free plan, rely on team discipline (don't push directly to main, use PRs, wait for green CI). Re-evaluate if (a) the team grows beyond Filippo + Peter, or (b) broken code lands on main despite discipline.
- `uv.lock` is now tracked in version control. The stock Python `.gitignore` template excluded it, which left CI unable to reproduce the resolved dependency set or hash-key the cache. For an application monorepo (vs a library), the lockfile belongs in git. Removed the gitignore entry and committed the existing root lockfile (253 lines).
- **Gotcha:** the `gh` CLI needs the `workflow` OAuth scope to push files under `.github/workflows/`. Default `gh auth login` doesn't include it. Add it with: `gh auth refresh -h github.com -s workflow`.

---

### 5. Bootstrap a separate `midas-deploy` repo for Kubernetes manifests

**What:** create a second private GitHub repo `bakerlunch-ai/midas-deploy`. This is where Kubernetes manifests live, separate from application code, per GitOps best practice. Folder structure: `clusters/prod/`, `clusters/paper/`, `infrastructure/`.

**Done when:**
- Repo exists, cloned locally, has README and folder skeleton
- Repo is private

**Why separate:** the application repo defines what the code does; the deploy repo defines how it runs. They change for different reasons. Argo CD watches the deploy repo, not the app repo.

---

### 6. Install Argo CD into the cluster

**What:** Argo CD is the GitOps controller. It watches the `midas-deploy` repo and applies changes to the cluster.

**Done when:**
- `kubectl get pods -n argocd` shows Argo CD running
- Argo CD UI is accessible (via `kubectl port-forward`, no public IP yet)
- Argo CD is configured with read access to the `midas-deploy` repo
- A test "hello-world" application defined in `midas-deploy` is automatically deployed by Argo CD when the manifest is committed

**Why:** this is the foundation of GitOps. After this, every deployment is "git commit to midas-deploy → Argo applies it → service is updated." No `kubectl apply` from a laptop.

---

### 7. Install sealed-secrets for credentials management

**What:** sealed-secrets is the controller that lets us commit encrypted secrets to git, decrypted only by the cluster.

**Done when:**
- sealed-secrets controller is running in the cluster
- `kubeseal` CLI is installed on your laptop
- A test secret (e.g. `test-credential: hello`) is sealed, committed to `midas-deploy`, and visible decrypted inside the cluster after Argo CD applies it
- The encrypted blob in git is unreadable by anyone without cluster access

---

### 8. Move database and Redis credentials into sealed-secrets

**What:** the connection strings from tasks 2 and 3 get sealed and committed.

**Done when:**
- All three Postgres connection strings are sealed-secrets in `midas-deploy`
- Redis connection string is a sealed-secret
- A test pod can read them as environment variables and connect to the actual services
- Original plaintext credentials are deleted from anywhere they were temporarily stored (laptop notes, scratch files)

---

### 9. Deploy NATS JetStream as a 3-replica cluster

**What:** install NATS using the official Helm chart, configured for JetStream (persistent streams) with 3 replicas.

**Done when:**
- `kubectl get pods -n nats` shows 3 NATS pods, all Ready
- From a test pod, you can publish a message to a test subject and receive it on another consumer
- JetStream persistence works: publish 10 messages, kill a NATS pod, verify the messages survive and are still consumable
- The NATS deploy manifest is in `midas-deploy/infrastructure/nats/`

---

### 10. Deploy the LGTM observability stack

**What:** Loki (logs), Grafana (visualization), Tempo (traces), Prometheus (metrics), and the OpenTelemetry collector.

**Done when:**
- All five components running in `infrastructure` namespace
- Grafana UI is accessible (via port-forward, no public IP yet)
- Prometheus is scraping the cluster's own metrics
- Loki is receiving logs from the cluster
- A test "hello-world" service emits a metric, a log line, and a trace span; all three are visible in Grafana
- Grafana has a dashboard showing cluster health (CPU, memory, pod restarts)

---

### 11. Deploy a hello-world service end-to-end

**What:** the proof-of-life test. A tiny Python service that emits a NATS event every 30 seconds, logs it, exposes a metric, and creates a trace span. Deployed via the full pipeline: code in `midas` repo → CI → built image → manifest in `midas-deploy` → Argo CD applies → running in cluster.

**Done when:**
- Pushing a code change to `midas` triggers CI, which builds and pushes a new Docker image
- The new image tag is referenced in `midas-deploy`
- Argo CD sees the change and deploys it without manual intervention
- The hello-world service appears in the Grafana dashboard, with logs, metrics, and traces all flowing
- Killing the hello-world pod causes Kubernetes to restart it automatically; this restart is visible in metrics

**Why this is the milestone:** this is the proof that all the infrastructure works together. After this, deploying a real service is the same shape, just with real logic.

---

### 12. Document the runbook

**What:** write `docs/RUNBOOK_PHASE_1.md` covering: how to access the cluster, how to view Grafana, how to view Argo CD, how to roll back a deployment, what to check first when something breaks. One page, written for the version of you that comes back to this in three weeks having forgotten everything.

**Done when:**
- The doc exists, is readable in under 5 minutes
- A second person (or future-you) could use it to access the system without asking for help

---

## What "done with Phase 1" looks like

- DOKS cluster running, costing ~$100-150/month
- NATS, Postgres, Redis, LGTM all running and healthy
- Argo CD is the only path to deploy code into the cluster
- Sealed-secrets holds all credentials; nothing sensitive lives in plaintext outside the cluster
- A hello-world service is running and observable end-to-end
- The runbook is written

At this point, Phase 2 begins: the first real Midas service (`data-svc` with the Kalshi adapter). The infrastructure should not change again unless we explicitly decide to change it.

---

## What we're NOT doing in Phase 1

- Public-facing endpoints. No DNS, no Ingress controller, no TLS-on-public-IP, no CloudFlare tunnel. Everything is access-via-port-forward for now. We add public access only when there's a real reason (an MCP server, a webhook).
- Multi-cluster, multi-region, or HA Postgres. Single region, single cluster. We can scale later.
- HashiCorp Vault. Sealed-secrets is enough for our scale.
- Custom Helm charts. Use community charts where they exist; write our own only when forced to.
- Auto-scaling. Fixed 3-node cluster. Manual scale if needed.

---

## Risks specific to Phase 1

- **Cost overruns from forgotten resources.** It's easy to provision something for a test and forget to delete it. Set a billing alert in DigitalOcean for $200/month before starting.
- **Misconfigured network policies leaking services to the public internet.** Verify each service is only accessible from within the cluster (or via deliberate port-forward) at every step.
- **Mishandled secrets ending up in git history.** If a secret is ever accidentally committed, it must be considered compromised — rotated immediately, not just removed in a follow-up commit. Git history is forever.

---

## When something goes wrong

Stop. Read `docs/LESSONS_FROM_OLD_BOT.md`. Specifically lessons 2 (reconciliation), 4 (dead code), and 5 (duplicated logic) — these are the patterns most likely to creep in during infrastructure work because there's a temptation to "just script it now and clean it up later." Don't.

If a task in this plan fails after a serious attempt: stop, ask Claude (chat) for help, do not invent a workaround that bypasses the plan. The plan is the plan because it produces a clean foundation. Workarounds compound.
