# Storefront Concierge

A chat-based shopping concierge and **Campus Demand Radar** for Shopify storefronts. Shoppers search a live Shopify catalog, build a real cart, and hand off to Shopify checkout. Merchants run a Demand Radar that mashes up campus events, weather, and shopper intent to surface what to feature this week — then triggers a Kestra workflow to act on it.

> **Showcase store:** [The Kohawk Shop](https://thekohawkshop.com) — Coe College, Cedar Rapids IA

---

## Architecture

```
CloudFront CDN ──► S3 (storefront-ui static files)
                        │
                        ▼
               api-gateway :8000  (FastAPI + LangGraph)
              /           |           \
   catalog-service    payment-service  order-service
      :8001               :8002            :8003
   (FastAPI)           (FastAPI)        (FastAPI)
        │                  │                │
        ▼                  ▼                ▼
   Redis (cache)      Redis (session)   Postgres (orders)
                                            │
                                        SQS queue ──► Kestra workflows
```

**Services:**

| Service | Port | Responsibility |
|---|---|---|
| storefront-ui | 3000 (local) / CloudFront (prod) | React + TypeScript chat UI |
| api-gateway | 8000 | Intent classification, LangGraph agent, session management |
| catalog-service | 8001 | Shopify MCP search with Redis cache + seed fallback |
| payment-service | 8002 | Cart quoting and checkout |
| order-service | 8003 | Order persistence (Postgres), SQS events, Kestra triggers |

**Infrastructure (production):**

| Component | AWS Service | Purpose |
|---|---|---|
| Container hosting | EKS (Kubernetes) | Runs services across multiple nodes; auto-scales and self-heals |
| Container images | ECR | Stores Docker images built by CI/CD |
| Frontend hosting | S3 + CloudFront | Serves the React app globally from the CDN edge |
| Order events | SQS FIFO | Async queue between order-service and downstream systems |
| Database | RDS PostgreSQL | Orders, sessions, intent log |
| Cache | ElastiCache Redis | Catalog search cache, session store |
| Secrets | HashiCorp Vault | API keys and credentials (never hardcoded) |
| Ingress | Kong | Rate limiting, CORS, request tracing at the cluster edge |

---

## Running locally

All services run with Docker Compose. No AWS account needed.

```bash
# Copy env file and set your Shopify store
cp .env.example .env
# Edit .env: set SHOPIFY_STORE_DOMAIN=thekohawkshop.com (already set in .env.example)

# Start everything
docker compose up --build

# UI:           http://localhost:3000
# API gateway:  http://localhost:8000
# API docs:     http://localhost:8000/docs
# Kestra UI:    http://localhost:8080
```

Try these prompts in the chat:
- `Find a campus mug`
- `Find a hoodie for an alum`
- `Add the best option to my cart`
- `Checkout in Shopify`
- `Run campus opportunity scan`
- `Simulate order paid`

**What works locally without any AWS setup:**

| Capability | Local status |
|---|---|
| Shopify catalog search (live) | ✅ Real — calls thekohawkshop.com Shopify MCP |
| Shopify cart + checkout URL | ✅ Real |
| Redis session + catalog cache | ✅ Real — Docker Compose redis container |
| Postgres order persistence | ✅ Real — Docker Compose postgres container |
| Kestra post-order workflows | ✅ Real — Docker Compose kestra container |
| SQS order events | Graceful no-op (logs a warning, continues) |
| CloudFront CDN | N/A — nginx serves UI locally |
| Vault secrets | N/A — env vars used directly locally |

---

## Deploying to AWS

### Prerequisites

Install these tools before starting:

```bash
# AWS CLI
brew install awscli
aws configure   # enter your Access Key ID, Secret, and region: us-east-1

# kubectl + eksctl (EKS management)
brew install kubectl eksctl

# Helm (installs Kong and Vault on the cluster)
brew install helm
```

Verify:
```bash
aws sts get-caller-identity   # should print your AWS account ID
```

---

### Step 1 — Create AWS infrastructure

Run these once. They provision the actual cloud resources.

```bash
# --- S3 bucket for the React UI + media assets ---
aws s3 mb s3://acme-static --region us-east-1
aws s3api put-public-access-block \
  --bucket acme-static \
  --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"
aws s3 website s3://acme-static \
  --index-document index.html --error-document index.html

# --- CloudFront distribution ---
aws cloudfront create-distribution \
  --origin-domain-name acme-static.s3-website-us-east-1.amazonaws.com \
  --default-root-object index.html \
  --query 'Distribution.{ID:Id,Domain:DomainName}' --output table
# Note the Distribution ID — you'll need it for GitHub secrets

# --- SQS FIFO queue for order events ---
aws sqs create-queue \
  --queue-name order-events.fifo \
  --attributes FifoQueue=true,ContentBasedDeduplication=true \
  --region us-east-1
# Note the queue URL from the output

# --- ECR repositories (one per service) ---
for svc in catalog-service payment-service order-service api-gateway; do
  aws ecr create-repository --repository-name acme/$svc --region us-east-1
done

# --- Get your account ID (needed for .env and GitHub secrets) ---
aws sts get-caller-identity --query Account --output text
```

---

### Step 2 — Create the EKS cluster

This provisions the actual servers that run your containers. Takes ~15 minutes.

```bash
eksctl create cluster \
  --name acme-prod \
  --region us-east-1 \
  --node-type t3.medium \
  --nodes 3 \
  --nodes-min 2 \
  --nodes-max 6

# Verify nodes are ready
kubectl get nodes
```

**What this creates:**
- 3 EC2 servers (`t3.medium`, ~$100/month total) in us-east-1
- Kubernetes control plane managed by AWS (~$73/month)
- Auto-scaling configured between 2–6 nodes

---

### Step 3 — Install Kong and Vault on the cluster

Kong is the traffic bouncer. Vault is the secrets safe. Both run inside the cluster.

```bash
# Kong Ingress Controller
helm repo add kong https://charts.konghq.com
helm repo update
helm install kong kong/ingress -n kong --create-namespace

# HashiCorp Vault
helm repo add hashicorp https://helm.releases.hashicorp.com
helm install vault hashicorp/vault -n vault --create-namespace \
  --set "server.dev.enabled=true"

# Wait for Vault to be ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=vault -n vault --timeout=120s

# Seed Vault with secrets (replace placeholder values)
kubectl exec -n vault vault-0 -- vault kv put vault/prod/acme/shopify \
  store_domain=thekohawkshop.com

kubectl exec -n vault vault-0 -- vault kv put vault/prod/acme/postgres \
  url=postgresql://commerce:YOURPASSWORD@your-rds-endpoint:5432/commerce

kubectl exec -n vault vault-0 -- vault kv put vault/prod/acme/redis \
  url=redis://your-elasticache-endpoint:6379/0

kubectl exec -n vault vault-0 -- vault kv put vault/prod/acme/aws \
  sqs_order_events_url=https://sqs.us-east-1.amazonaws.com/ACCOUNT_ID/order-events.fifo \
  aws_access_key_id=YOUR_KEY \
  aws_secret_access_key=YOUR_SECRET
```

---

### Step 4 — Configure GitHub secrets

Go to your GitHub repo → **Settings → Secrets and variables → Actions** and add:

| Secret name | Value |
|---|---|
| `AWS_ACCESS_KEY_ID` | Your AWS access key |
| `AWS_SECRET_ACCESS_KEY` | Your AWS secret key |
| `AWS_ACCOUNT_ID` | Your 12-digit AWS account ID |
| `CLOUDFRONT_DISTRIBUTION_ID` | The distribution ID from Step 1 |
| `API_GATEWAY_URL` | Public URL of your EKS load balancer, e.g. `https://abc.us-east-1.elb.amazonaws.com` — baked into the React build so the browser knows where to send API calls |

These are used by the CI/CD workflows to push images to ECR, deploy to EKS, and sync the UI to S3.

---

### Step 5 — Deploy the services

```bash
# Create the acme-prod namespace
kubectl apply -f infra/k8s/namespace.yaml
kubectl apply -f infra/k8s/configmap.yaml
kubectl apply -f infra/k8s/vault-external-secrets.yaml

# Deploy all services
# First set your ECR registry and image tag:
export ECR_REGISTRY=$(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com
export IMAGE_TAG=latest

# Build and push images manually for first deploy
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_REGISTRY

for svc in catalog-service payment-service order-service api-gateway; do
  docker build -t $ECR_REGISTRY/acme/$svc:$IMAGE_TAG ./services/$svc
  docker push $ECR_REGISTRY/acme/$svc:$IMAGE_TAG
done

# Apply Kubernetes manifests (envsubst fills in ECR_REGISTRY and IMAGE_TAG)
for f in infra/k8s/*.yaml; do
  envsubst < $f | kubectl apply -f -
done

# Check everything is running
kubectl get pods -n acme-prod
kubectl get ingress -n acme-prod
```

---

### Step 6 — Deploy the UI to S3 + CloudFront

```bash
cd storefront-ui
npm install
npm run build

# Sync to S3 (assets cached forever, index.html never cached)
aws s3 sync dist/ s3://acme-static/ \
  --delete \
  --cache-control "public,max-age=31536000,immutable" \
  --exclude "index.html"

aws s3 cp dist/index.html s3://acme-static/index.html \
  --cache-control "no-cache,no-store,must-revalidate"

# Bust the CloudFront cache so users get the new version
aws cloudfront create-invalidation \
  --distribution-id YOUR_DISTRIBUTION_ID \
  --paths "/*"
```

After this, your UI is live at your CloudFront domain (e.g. `https://d1234abcd.cloudfront.net`).

---

### After first deploy — CI/CD takes over

Once the GitHub secrets are set, every push to `main` triggers the pipelines automatically:

```
Push to main (services/**) →  ci.yml tests → cd-services.yml builds Docker image
                               → pushes to ECR → kubectl set image → EKS rolls out
                               → zero-downtime (health check gates the swap)

Push to main (storefront-ui/**) → cd-ui.yml builds React app
                                 → syncs to S3 → CloudFront invalidation
```

You never need to run `docker push` or `kubectl` manually again after this.

---

## What the Kubernetes files actually do

`infra/k8s/` contains one YAML file per service. Each file has three sections:

**Deployment** — tells EKS what to run:
- Which Docker image to pull from ECR
- How many copies (`replicas: 2` means 2 containers, spread across different nodes)
- Health check endpoint — EKS won't send traffic until `/health` returns 200
- CPU and memory limits — prevents one service from starving others on the same node

**Service** — internal DNS so services can find each other:
- `catalog-service:8001` resolves to whichever healthy copy of catalog-service is running
- No service ever hardcodes an IP address

**HorizontalPodAutoscaler** (catalog-service only):
- Watches CPU usage across all catalog-service copies
- Automatically adds more copies when CPU exceeds 60%
- Scales back down when traffic drops
- Range: 2–8 copies

---

## Configuration reference

Copy `.env.example` to `.env` for local development. In production these come from Vault.

| Variable | Default | Purpose |
|---|---|---|
| `SHOPIFY_STORE_DOMAIN` | _(unset)_ | Shopify store domain. When set, catalog uses live MCP search. When unset, uses seed catalog. |
| `DATABASE_URL` | _(unset)_ | Postgres connection string. When unset, order/intent persistence silently skipped. |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis for catalog cache and session storage |
| `CATALOG_CACHE_TTL_SECONDS` | `3600` | How long Shopify search results stay cached in Redis |
| `SQS_ORDER_EVENTS_URL` | _(unset)_ | SQS FIFO queue URL. When unset, order events silently skipped. |
| `AWS_REGION` | `us-east-1` | AWS region for SQS |
| `KESTRA_URL` | `http://localhost:8080` | Kestra base URL for workflow triggers |
| `KESTRA_NAMESPACE` | `demo.commerce` | Kestra namespace |
| `KESTRA_FLOW_ID` | `chat-commerce-order-fulfillment` | Post-order workflow ID |
| `KESTRA_RADAR_FLOW_ID` | `campus-demand-radar` | Demand radar workflow ID |
| `CATALOG_SERVICE_URL` | `http://localhost:8001` | Set automatically in Docker Compose and K8s |
| `PAYMENT_SERVICE_URL` | `http://localhost:8002` | Set automatically in Docker Compose and K8s |
| `ORDER_SERVICE_URL` | `http://localhost:8003` | Set automatically in Docker Compose and K8s |
| `VITE_API_GATEWAY_URL` | `http://localhost:8000` | API base URL baked into the React build |

---

## Project structure

```
services/
  api-gateway/          FastAPI — agent orchestration, session, intent log
  catalog-service/      FastAPI — Shopify MCP search, Redis cache
  payment-service/      FastAPI — cart quote, checkout
  order-service/        FastAPI — orders, SQS publish, Kestra trigger
storefront-ui/          React + TypeScript + Vite
infra/
  k8s/                  Kubernetes manifests (Deployment, Service, HPA, Ingress)
.github/workflows/
  ci.yml                Tests on pull request (pytest + tsc)
  cd-services.yml       Build → ECR → EKS on push to main
  cd-ui.yml             Build → S3 → CloudFront on push to main
kestra/flows/           Post-order and demand radar workflow definitions
db/init/                Postgres schema (auto-applied on first DB connection)
data/seed_catalog.json  Fallback product catalog (used when Shopify is unreachable)
docker-compose.yml      Full local stack (all services + postgres + redis + kestra)
.env.example            Environment variable reference
```

---

## License

[MIT](./LICENSE)