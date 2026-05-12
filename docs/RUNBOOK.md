# Midas — Operations Runbook

> **What this is:** the operations manual for Midas. Everything you need to do day-to-day, ship a new service, rotate a credential, or respond to an incident.
>
> **Who it's for:** Filippo (decision-maker, DigitalOcean console, password manager), Peter (terminal, kubectl, git), and any future Claude chat opened to help with operations.
>
> **Updated:** May 12, 2026 (end of Phase 1)
>
> **Read alongside:** `docs/PROJECT_HANDOFF.html` (current state), `docs/JOURNEY.md` (why we built it this way), `docs/TODO.md` (what's next).

---

## Conventions used in this doc

- All `kubectl` commands assume `KUBECONFIG=~/.kube/config-midas` is exported in the shell, OR prefixed inline. Commands here show the inline form for cut-and-paste safety on a fresh terminal.
- `/opt/homebrew/bin/` is included on commands that use a Homebrew-installed binary — strip the prefix if your shell PATH is set up.
- All paths assume the local repo at `~/Desktop/midas/` (Filippo's Mac) or `~/code/midas/` (Peter's Mac). Substitute whichever applies.
- Anything tagged 🚨 is a stop-and-think moment, not a routine action.

---

## Part 1 — Daily check (5 minutes)

Do this once a day when actively developing, or at least 2-3x per week when idle. Faster than reading the news.

### 1.1 Cluster + nodes

```bash
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl get nodes
```

**Expected:** 3 nodes, all `Ready`, all `v1.35.1` (or whatever the current DOKS version is). If any node shows `NotReady`, DigitalOcean is doing maintenance — usually self-recovers in 5-10 minutes. If it sticks for >30min, check the DigitalOcean status page.

### 1.2 Argo CD applications

```bash
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl get applications -n argocd
```

**Expected sync/health for each:**

| App | Sync | Health | Notes |
|---|---|---|---|
| `hello-world` | Synced | Healthy | Smoke test app |
| `hello-svc` | Synced | Healthy | First real service |
| `kube-prometheus-stack` | Synced | Healthy | |
| `loki` | Synced | Healthy | |
| `nats` | OutOfSync ⚠️ | Healthy | Cosmetic drift — known carry item, pods are fine |
| `sealed-secrets` | Synced | Healthy | |
| `tempo` | Synced | Healthy | |

The only acceptable `OutOfSync` is `nats` (Helm chart drift; pods serve correctly). Anything else `OutOfSync` deserves a look — see Part 4 incident response.

### 1.3 Pod health across all namespaces

```bash
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl get pods --all-namespaces | grep -v Running
```

**Expected:** no output, or just the header row. Any pod in `Pending`, `CrashLoopBackOff`, `ImagePullBackOff`, `Error`, `Completed` (Job-related, fine), or `Terminating` deserves a look.

### 1.4 hello-svc heartbeat sanity check (optional — once a week)

If you want to confirm the event bus is actually working end-to-end, subscribe for one heartbeat:

```bash
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl run nats-sub-test \
  --rm -i --restart=Never \
  --image=natsio/nats-box:latest \
  -n nats -- \
  nats sub --server=nats://nats:4222 'events.heartbeat.>' --count=1 --timeout=90s
```

**Expected:** one message within 60 seconds, on subject `events.heartbeat.hello-svc`, with a HeartbeatEvent JSON payload.

### 1.5 What "all green" looks like

- 3 nodes Ready
- 7 Argo apps Synced + Healthy (or 6 Synced + 1 OutOfSync for NATS, Healthy)
- No abnormal pods
- Heartbeat flowing (if checked)

That's the daily state. Move on with your day.

---

## Part 2 — Deploy a new service (the hello-svc pattern)

Every new Python service in Midas follows this shape. hello-svc is the working reference; copy its structure.

### 2.1 What you'll create

For a service called `<svc>` (e.g. `data-svc`, `oms-svc`):

```
services/<svc>/
├── pyproject.toml                        # uv workspace member
├── README.md
├── Dockerfile                            # Multi-stage uv build
├── src/<svc>/
│   ├── __init__.py
│   ├── config.py                         # Pydantic-settings
│   ├── main.py                           # FastAPI app + lifespan
│   └── ...service-specific modules...
└── tests/
    ├── conftest.py                       # settings_factory, env_settings fixtures
    └── test_*.py

deploy/<svc>/
├── namespace.yaml
├── deployment.yaml
└── service.yaml

deploy/applications/<svc>.yaml            # Argo CD Application

deploy/secrets/<svc>/                     # SealedSecrets for this namespace
└── *.yaml

.github/workflows/build-<svc>.yml         # Docker build → push to GHCR
```

### 2.2 The deploy sequence

1. **Code first.** Write the service, lint clean, tests green. TDD discipline: red → green → refactor.
2. **Push to feat branch** → CI runs `make install && make lint && make test`. Wait for green.
3. **Merge to main** (fast-forward) → `build-<svc>.yml` triggers → image pushes to `ghcr.io/bakerlunch-ai/<svc>:main` + `:sha-<full>`.
4. **Set GHCR package visibility.** New packages default to private. For services with non-proprietary logic, flip to public:
   - `https://github.com/users/bakerlunch-ai/packages/container/<svc>/settings`
   - Danger Zone → Change visibility → Public → type `<svc>` to confirm.
   - For services with proprietary logic (oms-svc, strategy-*), keep private and use an `imagePullSecret` — see Part 3.5.
5. **Re-seal secrets for the new namespace.** See Part 3 if the service needs Postgres/Redis credentials.
6. **Apply the Argo Application.** Either commit `deploy/applications/<svc>.yaml` to main and let app-of-apps pick it up, or `kubectl apply -f` directly the first time:
   ```bash
   KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl apply \
     -f deploy/applications/<svc>.yaml
   ```
7. **Watch it come up:**
   ```bash
   KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl get application <svc> -n argocd
   KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl get pods -n <svc>
   KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl logs -n <svc> -l app=<svc> --tail=50
   ```

### 2.3 Conventions to copy from hello-svc

- **Container name `app`** (not the service name) — avoids `kubectl logs <svc> -c <svc>` collision.
- **Pod spec `runAsNonRoot: true`, `runAsUser: 1000`, `runAsGroup: 1000`** — matches the Dockerfile's user.
- **Container `readOnlyRootFilesystem: true`** + `capabilities.drop: [ALL]` + `allowPrivilegeEscalation: false`.
- **Liveness + readiness probes** on `/health` (or `/ready` if dependency-aware — carry item).
- **`envFrom: secretRef`** for credentials, never plain `env`.
- **Resource requests:** start small (cpu `50m`, memory `128Mi`) and scale up if Prometheus shows throttling.
- **Image tag `:main` + `imagePullPolicy: Always`** for v1 — known anti-pattern, fix before first real strategy.

### 2.4 New service consuming `bot-events` workspace package

In the new service's `pyproject.toml`:

```toml
[project]
dependencies = [
    "bot-events",
    # ... other deps
]

[tool.uv.sources]
bot-events = { workspace = true }
```

And in the GHA build workflow `paths:` trigger, include:

```yaml
paths:
  - "services/<svc>/**"
  - "packages/bot-events/**"
  - ".dockerignore"
  - ".github/workflows/build-<svc>.yml"
```

This is manual per service — no automatic "rebuild all consumers of bot-events" mechanism exists.

---

## Part 3 — Credential management

### 3.1 The sealing pipeline (canonical pattern)

Every sealed-secret is created by piping the plaintext credential through `kubectl create secret --dry-run=client` to produce an unencrypted Secret YAML, then through `kubeseal` to encrypt it for a specific namespace+name binding.

**Critical safety rules:**

1. **Never put plaintext credentials on disk.** Use `pbpaste` to stream from clipboard, never `cat /tmp/password.txt`.
2. **Always strip trailing whitespace.** `pbpaste` preserves trailing newlines from password managers; `printf '%s' "$(pbpaste)"` strips them. The May-4 oms breakage mode was a trailing newline in the sealed payload.
3. **Always decode-verify after applying.** Length in bytes tells you whether something weird got piped in.
4. **Always clear clipboard immediately after seal.** `echo -n "" | pbcopy`.

### 3.2 Seal a credential (the exact pipeline)

For a service called `<svc>` that needs a secret named `<secret-name>` with env var key `<ENV_VAR_KEY>`:

```bash
# Pre-flight: ensure namespace exists
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl apply \
  -f ~/Desktop/midas/deploy/<svc>/namespace.yaml

mkdir -p ~/Desktop/midas/deploy/secrets/<svc>/

# Filippo: copy the credential to clipboard from password manager

# Peter: run the seal pipeline
printf '%s' "$(pbpaste)" | KUBECONFIG=~/.kube/config-midas \
  /opt/homebrew/bin/kubectl create secret generic <secret-name> \
  --namespace <svc> \
  --from-file=<ENV_VAR_KEY>=/dev/stdin \
  --dry-run=client -o yaml | \
  KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubeseal \
  --controller-namespace=sealed-secrets \
  --controller-name=sealed-secrets-controller \
  --format=yaml > ~/Desktop/midas/deploy/secrets/<svc>/<secret-name>.yaml

# Filippo: clear clipboard immediately
echo -n "" | pbcopy

# Apply the sealed secret to the cluster
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl apply \
  -f ~/Desktop/midas/deploy/secrets/<svc>/<secret-name>.yaml

# Decode-verify: byte length should match the original credential length
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl get secret \
  <secret-name> -n <svc> \
  -o jsonpath='{.data.<ENV_VAR_KEY>}' | base64 -d | wc -c
```

**Expected byte counts (reference):**

| Secret type | Format | Expected length |
|---|---|---|
| Postgres URL | `postgresql://user:pw@host:port/db?sslmode=require` | ~140-145 bytes |
| Redis URL | `rediss://default:pw@host:port` | ~105-115 bytes |

If `wc -c` returns 0, the seal failed silently — re-seal. If it's >250 for either of the above, something extra got piped in — re-seal. Length matching expected range = good.

### 3.3 Commit and push the sealed YAML

The encrypted blob is safe to commit — only the cluster's sealed-secrets controller (master key suffix `2f279`) can decrypt it.

```bash
cd ~/Desktop/midas
git add deploy/secrets/<svc>/<secret-name>.yaml
git commit -m "feat(secrets): seal <secret-name> for <svc> namespace"
git push origin main
```

### 3.4 Rotate a credential (Postgres or Redis password)

When a password is leaked, suspected compromised, or just due for rotation.

**Step 1 — Generate new password in DigitalOcean console:**
- Postgres: `cloud.digitalocean.com` → Databases → `midas-postgres` → Users & Databases → click user → Reset Password. Copy new password to clipboard. Save to password manager.
- Redis: same flow under `midas-redis` → Settings → Reset Password.

**Step 2 — Build the new connection string and copy to clipboard:**
- Postgres: `postgresql://<user>:<NEW_PW>@<VPC-host>:25060/<db>?sslmode=require`
- Redis: `rediss://default:<NEW_PW>@<VPC-host>:25061`

**Step 3 — Re-seal for every namespace that uses it.** Currently that's `default` (legacy, pre-hello-svc) and `hello-svc`. Use the pipeline in 3.2 for each. Future services will add more.

**Step 4 — Trigger a rollout** so pods pick up the new credential:

```bash
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl rollout restart deployment \
  -n <svc> <deployment-name>
```

The new pod reads the updated Secret on startup; the old pod stays up until the new one is Ready (default rolling update strategy).

**Step 5 — Verify the new pod is healthy:**
```bash
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl get pods -n <svc>
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl logs -n <svc> -l app=<svc> --tail=30
```

If startup checks fail (Postgres SELECT 1, Redis PING), roll back immediately by reverting the sealed-secret commit and `kubectl apply` the old version. Then debug.

### 3.5 imagePullSecret for private GHCR images

When a service's container image must stay private (proprietary trading logic — oms-svc, strategy-*), the cluster needs auth to pull from GHCR.

**Step 1 — Generate a GitHub Classic PAT** at `https://github.com/settings/tokens`:
- Scope: `read:packages` only
- Name: `ghcr-pull-midas-prod-<svc>` (per-service for blast-radius isolation)
- Expiration: 1 year, set calendar reminder

**Step 2 — Seal it as a `dockerconfigjson` secret:**

```bash
# Filippo: copy PAT to clipboard

GHCR_USERNAME=bakerlunch-ai
GHCR_PAT="$(pbpaste)"

# Build the docker config JSON and seal it
echo -n "${GHCR_USERNAME}:${GHCR_PAT}" | base64 | \
  awk -v user="$GHCR_USERNAME" '{print "{\"auths\":{\"ghcr.io\":{\"username\":\""user"\",\"auth\":\""$1"\"}}}"}' | \
  KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl create secret generic ghcr-pull \
  --namespace <svc> \
  --type=kubernetes.io/dockerconfigjson \
  --from-file=.dockerconfigjson=/dev/stdin \
  --dry-run=client -o yaml | \
  KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubeseal \
  --controller-namespace=sealed-secrets \
  --controller-name=sealed-secrets-controller \
  --format=yaml > ~/Desktop/midas/deploy/secrets/<svc>/ghcr-pull.yaml

echo -n "" | pbcopy
unset GHCR_PAT
```

**Step 3 — Add to deployment.yaml pod spec:**

```yaml
spec:
  template:
    spec:
      imagePullSecrets:
        - name: ghcr-pull
      containers:
        - ...
```

---

## Part 4 — Incident response

When something is broken, use these symptom → diagnosis → fix flows. The diagnostic commands are read-only and safe.

### 4.1 🚨 Pod stuck in `Pending`

```bash
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl describe pod -n <ns> <pod-name> | tail -30
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl get events -n <ns> --sort-by='.lastTimestamp' | tail -10
```

**Common causes:**
- **Insufficient resources** — no node has cpu/memory headroom for the requested resources. Either lower the request in deployment.yaml, or request a DigitalOcean droplet limit increase (we're capped at 3).
- **Image pull pending** — see 4.2.
- **PersistentVolumeClaim pending** — check `kubectl get pvc -n <ns>`. CSI driver may be slow on first claim.
- **Scheduling constraint** — node selector, taint, affinity mismatch. Rare for our setup.

### 4.2 🚨 Pod stuck in `ImagePullBackOff` or `ErrImagePull`

```bash
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl describe pod -n <ns> <pod-name> | grep -A 10 Events
```

**Common causes:**
- **401 Unauthorized** — image is private and namespace has no `imagePullSecret`. Either flip GHCR package to public (cheap path for non-proprietary services) or set up `imagePullSecret` per Part 3.5.
- **Manifest not found** — image tag doesn't exist. Check the GHA build workflow ran successfully: `gh run list --workflow build-<svc>.yml`. If CI hasn't pushed yet, wait.
- **DNS / network** — rare. Check `kubectl get nodes` — if nodes are unhealthy, DOKS is degraded.

**Force immediate retry after fixing:**
```bash
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl delete pod -n <ns> -l app=<svc>
```

### 4.3 🚨 Pod in `CrashLoopBackOff`

```bash
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl logs -n <ns> -l app=<svc> --tail=80
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl logs -n <ns> -l app=<svc> --previous --tail=80
```

The `--previous` flag shows logs from the previous (crashed) container instance — usually where the actual error message lives.

**Common causes:**
- **Startup check failed** — Postgres SELECT 1, Redis PING, or NATS connect threw an exception. Check sealed-secrets are present and decoded correctly. Check VPC connectivity (DB allowed sources).
- **Missing env var** — Pydantic-settings will raise on missing required fields. Check the deployment.yaml `envFrom: secretRef` references match the sealed-secret names.
- **Read-only filesystem error** — some library tried to write somewhere. Either fix the library, or add an `emptyDir` volume mounted where it needs to write (typically `/tmp`).
- **OOMKilled** — pod exceeded memory limit. Either raise the limit in deployment.yaml, or investigate why memory is climbing.

### 4.4 🚨 Argo CD application `OutOfSync` (other than NATS)

```bash
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl describe application -n argocd <app> | tail -40
```

Argo will show the diff between git and live state under `Resources`. Look for what specifically differs.

**Common causes:**
- **Someone hand-edited a resource** in the cluster. Run an Argo sync to overwrite live with git: `argocd app sync <app>` (or in the UI). With `selfHeal: true` set on the app, this should auto-heal — if it doesn't, the diff is in an immutable field.
- **Immutable field changed in git** (e.g. Service `clusterIP`). Need to delete + recreate the resource.
- **Admission webhook injecting fields** Argo doesn't ignore. This is NATS's case — cosmetic only.

### 4.5 🚨 Database unreachable from pods

If multiple services suddenly fail their startup checks against Postgres or Redis:

**Check the DB itself is up:**
- DigitalOcean console → Databases → cluster status should be `Online`.

**Check VPC connectivity:**
- Trusted sources on the DB should include `midas-prod` cluster. If a node pool was rebuilt, the source might need re-adding.

**Test from inside the cluster:**
```bash
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl run db-test \
  --rm -i --restart=Never \
  --image=postgres:18-alpine \
  -n hello-svc -- \
  psql 'postgresql://oms_user:...@private-midas-postgres-...:25060/oms_db?sslmode=require' -c 'SELECT 1'
```

(Use the credentials from `hello-svc`'s sealed secret. The pod will see them via envFrom if you set `env:` in the test pod manifest — or just paste the URL for one-shot debug.)

### 4.6 🚨 Roll back a bad deploy

Argo CD keeps deployment history. To roll back:

**Option A — Revert the git commit that caused the bad deploy:**
```bash
cd ~/Desktop/midas
git log --oneline | head -5         # find the bad commit
git revert <bad-commit-sha>
git push origin main
```

Argo sees the revert and applies it. ~30-60s to recovery.

**Option B — Direct rollback via kubectl (faster, for emergencies):**
```bash
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl rollout undo deployment \
  -n <ns> <deployment-name>
```

This rolls back to the previous deployment revision but does NOT update git. Argo will then see drift and re-apply the bad version unless you also revert in git. **Always pair Option B with Option A** for permanent recovery.

### 4.7 🚨 Cluster API unreachable (`Unable to connect to the server: EOF`)

Usually a transient DOKS control-plane reshuffle (managed upgrades or leader-election events). Self-recovers in 30-60s. Wait, retry the command. If sustained >5min, check DigitalOcean status page.

### 4.8 🚨 NATS Argo app shows OutOfSync — what to do

**Nothing.** Pods are healthy and serving traffic. This is cosmetic drift in the upstream Helm chart vs what Argo last synced. Carry item: revisit if NATS upgrade actually changes something behavioral. As of session 5, the OutOfSync state has been stable for 2+ weeks with no impact.

---

## Part 5 — Common operations cheat sheet

### Watch all activity in a namespace
```bash
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl get all -n <ns> -w
```

### Restart all pods in a deployment (after secret change, after config change)
```bash
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl rollout restart deployment \
  -n <ns> <deployment-name>
```

### Scale a deployment up or down
```bash
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl scale deployment \
  -n <ns> <deployment-name> --replicas=<N>
```

### Tail logs across all pods of a service
```bash
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl logs -n <ns> -l app=<svc> --tail=100 -f
```

### Access Grafana (port-forward, since no ingress)
```bash
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl port-forward -n monitoring svc/kps-grafana 3000:80
# Then http://localhost:3000 in browser
# Default admin user: admin, password: in the kps-grafana secret
```

```bash
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl get secret -n monitoring kps-grafana \
  -o jsonpath='{.data.admin-password}' | base64 -d
```

### Access Argo CD UI (port-forward)
```bash
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl port-forward -n argocd svc/argocd-server 8080:443
# Then https://localhost:8080 in browser (accept self-signed cert)
```

### Access Prometheus (port-forward)
```bash
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl port-forward -n monitoring svc/kps-kube-prometheus-stack-prometheus 9090:9090
```

### Subscribe to NATS topics for debugging
```bash
KUBECONFIG=~/.kube/config-midas /opt/homebrew/bin/kubectl run nats-debug \
  --rm -i --restart=Never \
  --image=natsio/nats-box:latest \
  -n nats -- \
  nats sub --server=nats://nats:4222 '<subject-pattern>'
```

### Generate kubeconfig on a new Mac (~45 min sequence)
```bash
# Homebrew install path
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Add brew to PATH (Apple Silicon)
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"

# Install tools
brew install kubectl doctl gh uv kubeseal
brew install --cask orbstack   # or docker, or colima

# Authenticate
doctl auth init    # interactive, paste DO token
gh auth login      # interactive, web browser flow

# Generate kubeconfig (note: --kubeconfig flag was removed in doctl 1.158)
KUBECONFIG=~/.kube/config-midas doctl kubernetes cluster kubeconfig save midas-prod

# Verify
KUBECONFIG=~/.kube/config-midas kubectl get nodes
```

---

## Part 6 — Reference

### Cluster

- **Cluster name:** `midas-prod`
- **Region:** London (LON1)
- **Nodes:** 3 × Basic Premium Intel
- **K8s version:** v1.35.1 (DOKS managed)
- **Kubeconfig:** `~/.kube/config-midas`

### Repos

- **GitHub:** `github.com/bakerlunch-ai/midas` (private)
- **Local (Filippo):** `~/Desktop/midas/`
- **Local (Peter):** `~/code/midas/`

### Managed databases

- **Postgres:** `midas-postgres`, PG18, $30/mo, VPC-locked to `midas-prod`
  - DBs: `oms_db`, `pms_db`, `reporting_db`, `defaultdb`
  - Users: `oms_user`, `pms_user`, `reporting_user`, `doadmin`
  - Port: 25060
- **Redis:** `midas-redis`, smallest tier, ~$15/mo, VPC-locked to `midas-prod`
  - Port: 25061
  - TLS required (`rediss://`)

### Image registry

- **GHCR:** `ghcr.io/bakerlunch-ai/<svc>`
- **Tags pushed per build:** `:main` (mutable) and `:sha-<full-40>` (immutable)
- **Visibility default:** private. Flip to public for non-proprietary services.

### Sealed-secrets

- **Controller:** `sealed-secrets/sealed-secrets-controller` v0.36.6
- **Master cert suffix:** `2f279`
- **kubeseal CLI:** Homebrew-installed, version must match controller (currently 0.36.6)
- **Per-namespace scope:** strict (namespace+name binding) — same credential must be re-sealed per consuming namespace

### Argo CD

- **Namespace:** `argocd`
- **App-of-apps source:** `deploy/applications/` in this repo
- **Sync policy:** automated, prune=true, selfHeal=true, CreateNamespace=true

### Observability

- **Grafana:** port-forward via `kps-grafana` svc in `monitoring` ns
- **Prometheus:** port-forward via `kps-kube-prometheus-stack-prometheus` svc in `monitoring` ns
- **Loki:** in-cluster only, accessed via Grafana data source
- **Tempo:** in-cluster only, accessed via Grafana data source

### NATS

- **In-cluster URL:** `nats://nats.nats.svc.cluster.local:4222`
- **Auth:** none (Phase 1)
- **Replicas:** 3 (JetStream HA)

### Costs (as of May 2026)

| Item | Cost |
|---|---|
| Kubernetes cluster | $72/mo |
| Postgres | $30/mo |
| Redis | $15/mo |
| Misc (storage, load balancers eventually) | ~$10/mo |
| **Total** | **~$130/mo** (target <$150) |

### Known carry items

See `docs/TODO.md` "Carry items" section for the live list. Most relevant for ops:

- Postgres + Redis passwords leaked May 9 in chat transcript — rotate when convenient
- `/health` is dumb liveness — split into `/ready` before first real strategy
- `imagePullPolicy: Always` + `:main` mutable tag — fix before first real strategy
- Local gh token missing `read:packages` / `write:packages` scopes
- DO droplet limit at 3 — request bump before scaling
- DO account status "warning" — investigate
- DigitalOcean API token expires ~July 27, 2026

---

## Updating this runbook

When something changes in operations — a new service deployed, a new failure mode discovered, a credential rotation procedure refined — update this doc. It's living. The "Updated" date at the top is the source of truth for how fresh the content is.

Don't let it go stale. The whole point is that future-you (or a new team member) can run Midas operations without spelunking through commit history.
