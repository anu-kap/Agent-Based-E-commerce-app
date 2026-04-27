# Storefront Concierge

A chat-based shopping concierge and **Campus Demand Radar** for Shopify storefronts. The chat agent searches a live Shopify catalog over the [Storefront MCP](https://shopify.dev/docs/api/mcp), builds a real cart, and hands off to Shopify checkout. The Demand Radar mashes up campus events, weather, recent shopper intent, and live inventory to tell a merchant what to feature this week — and triggers a [Kestra](https://kestra.io) workflow to act on it.

> **Showcase store:** [The Kohawk Shop](https://thekohawkshop.com) (Coe College, Cedar Rapids, IA)

---

## What this demonstrates

- **An agentic chat surface that does real merchant work** — not a toy demo. Search → cart → checkout, all wired to a live Shopify store.
- **MCP as a clean tool boundary.** The agent calls the same tool functions that an external MCP client (Claude Desktop, etc.) could call.
- **A LangGraph state machine with a deterministic fallback.** The graph runs the same path whether `langgraph` is installed or not, so the demo always boots.
- **Workflow handoff at the merchant layer.** Shopify owns checkout, payment, tax, and order creation. After `orders/paid`, Kestra picks up — fulfillment, comms, alerts, demand-radar reporting.
- **A multi-source signal mash-up** the way real merchandising teams want it — public web (campus calendar) + weather + first-party intent + commerce inventory.

## Architecture

```mermaid
flowchart LR
  user([Shopper / Merchant]) -->|"chat message"| web[Browser UI<br/>vanilla JS]
  web -->|"POST /api/chat"| node[Node web server<br/>server.js]
  node -->|"spawn + stdin JSON"| agent[Python LangGraph agent<br/>commerce_agent.py]
  agent -->|"in-process import"| mcp[MCP tools<br/>commerce_mcp_server.py]
  mcp -->|"JSON-RPC"| shopify[(Shopify Storefront MCP)]
  mcp -->|"HTTP"| events[Coe events page]
  mcp -->|"HTTP"| weather[Open-Meteo]
  mcp -->|"cache + persist"| postgres[(Postgres)]
  mcp -->|"HTTP POST"| kestra[(Kestra workflows)]
  kestra --> postgres
```

**Catalog source-of-truth chain** (when `SHOPIFY_STORE_DOMAIN` is set):
fresh Postgres cache (1h TTL) → Shopify Storefront MCP → stale Postgres cache → seed catalog. Postgres and Kestra are both optional; the app works with neither.

For a deeper walkthrough — sequence diagrams of the four user flows (search, cart, checkout, radar), the LangGraph node map, MCP tool contracts, and the design decisions behind the cache and fallback chain — see [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md).

## What's real vs. what's mocked

| Capability | Status | Notes |
|---|---|---|
| Live Shopify catalog search | Real | `SHOPIFY_STORE_DOMAIN=thekohawkshop.com` calls Shopify's Storefront MCP |
| Live Shopify cart + checkout URL | Real | Returned by the same MCP endpoint |
| Postgres read-through cache | Real | When `DATABASE_URL` is set: 1h TTL on Shopify search responses; falls back to stale entries when Shopify hiccups |
| Seed catalog (last-resort fallback) | Real | `data/seed_catalog.json` — used only when Shopify is unreachable AND cache is empty (or no `SHOPIFY_STORE_DOMAIN` is set at all) |
| LangGraph state machine | Real if `langgraph` installed; otherwise deterministic fallback runs the same nodes |
| Coe College events signal | Real | Scrapes the public events calendar |
| Cedar Rapids weather signal | Real | Open-Meteo public API |
| Shopper intent log | Real | Persisted to `chat_intents` when `DATABASE_URL` is set; falls back to in-memory log otherwise |
| Local demo order persistence | Real | Persisted to `orders` table when `DATABASE_URL` is set |
| Kestra post-order automation | Real workflow trigger; needs `docker compose up kestra` to actually run |
| Shopify `orders/paid` webhook | **Simulated** by the "Simulate order paid" button — proves the handoff shape, not a real webhook |

## Quick start

```bash
# 1. Seed-catalog mode (no external services, no DB)
npm start
# → http://localhost:3000

# 2. Live Shopify mode (Kohawk Shop) — no DB cache, no persistence
SHOPIFY_STORE_DOMAIN=thekohawkshop.com npm start

# 3. Live Shopify + Postgres cache + intent/order persistence
docker compose up -d postgres
DATABASE_URL=postgresql://commerce:commerce@localhost:5432/commerce \
  SHOPIFY_STORE_DOMAIN=thekohawkshop.com npm start
# Schema auto-bootstraps from db/init/001_schema.sql on first DB call.

# 4. Add Kestra on top for the full post-order + radar workflow demo
docker compose up -d
# Kestra UI at http://localhost:8080, Postgres at localhost:5432
```

Try these prompts in the chat:

- `Find a hoodie for an alum`
- `Find waterproof trail shoes under $150` _(local catalog mode)_
- `Add the best option to my cart`
- `Checkout in Shopify`
- `Run campus opportunity scan` ← the radar demo
- `Simulate order paid` ← triggers the Kestra post-order workflow

### Run the agent from the terminal (no UI)

```bash
npm run agent:demo
```

### Tests

```bash
npm test
```

The contract tests run the agent end-to-end against the local catalog path — no external services required.

## Project shape

```
server.js                          Node web/API server (no framework)
public/                            Browser UI (vanilla HTML/CSS/JS)
agent/commerce_agent.py            LangGraph agent entry point
agent/mcp/commerce_mcp_server.py   MCP tools (importable + JSON-RPC entry)
agent/db.py                        Optional Postgres helpers (cache + persistence)
data/seed_catalog.json             Last-resort fallback catalog
db/init/001_schema.sql             Idempotent schema (auto-applied on first DB call)
kestra/flows/                      Kestra workflow YAML definitions
docker-compose.yml                 Postgres + Kestra for local optional services
Dockerfile                         Node + Python image for cloud deploy
render.yaml                        Render Blueprint (web service, free tier)
tests/                             Agent contract tests
```

## Configuration

All config is via env vars; copy `.env.example` to `.env` and edit.

| Var | Default | Purpose |
|---|---|---|
| `PORT` | `3000` | HTTP port |
| `SHOPIFY_STORE_DOMAIN` | _(unset)_ | If set, the agent calls Shopify Storefront MCP instead of the seed catalog |
| `DATABASE_URL` | _(unset)_ | Postgres URL. When set: caches Shopify search responses, persists `chat_sessions` / `chat_intents` / `orders`. When unset: all DB ops silently no-op |
| `CATALOG_CACHE_TTL_SECONDS` | `3600` | How long a Shopify search response stays "fresh" in the cache before triggering a refetch |
| `KESTRA_URL` | `http://localhost:8080` | Kestra base URL |
| `KESTRA_NAMESPACE` | `demo.commerce` | Kestra namespace for the demo flows |
| `KESTRA_FLOW_ID` | `chat-commerce-order-fulfillment` | Post-order flow ID |
| `KESTRA_RADAR_FLOW_ID` | `campus-demand-radar` | Demand radar flow ID |

## Deploy

### Render (one-click via Blueprint, free tier)

1. Push this repo to GitHub.
2. In Render, **New → Blueprint** and point at the repo. It reads [`render.yaml`](./render.yaml) and provisions a free web service running this Dockerfile.
3. Wait ~5–8 min for the first build. The service comes up at `https://storefront-concierge.onrender.com` (or your assigned subdomain).

The blueprint sets `SHOPIFY_STORE_DOMAIN=thekohawkshop.com` so the deployed demo runs in live-Shopify mode out of the box. Override or unset that env var in the Render dashboard to switch to the local catalog.

**Free-tier tradeoff:** the service spins down after 15 minutes of inactivity and cold-starts in ~30s on the next request. Upgrade to Render's `starter` plan ($7/mo) for always-on if you're sharing the demo broadly.

**Postgres is not in the blueprint.** The app does not read from a database today (the schema lives in `db/init/` for when MCP tools start persisting). Render's free Postgres still requires payment info on file, so the blueprint omits it. Add one later from the dashboard if you need it.

**Kestra is also not deployed.** Kestra wants ~2GB RAM and Postgres-backed queues — too much for Render's free or starter tier. Run it locally with `docker compose up kestra` to demo the workflow trigger end-to-end. The deployed app degrades cleanly to "Kestra workflow ready but not running" when Kestra is unreachable.

### Railway / Fly.io / any Docker host

The Dockerfile is platform-agnostic. Set `PORT` and (optionally) `SHOPIFY_STORE_DOMAIN`, and you're good.

## Where to extend

- Swap the deterministic intent classifier in `commerce_agent.py` for an LLM planner.
- Persist Shopify cart IDs across chat turns so cart state survives reloads.
- Promote the per-query cache to per-product (cache by SKU/variant ID with a separate query→IDs index) for higher reuse.
- Add identity, promotions, returns, recommendations, and payment-provider mocks.
- Generalize the radar beyond campus — events + weather + intent works for any geo-bound retailer.

## License

[MIT](./LICENSE)
