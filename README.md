# Agentic Commerce Chat

A demoable chat-based ecommerce experience using:

- NodeJS for the web server and chat API
- Python with LangGraph-style agent orchestration
- MCP-style JSON-RPC commerce tools for catalog search, cart quote, and order creation
- Optional Shopify Storefront MCP integration for real store catalog/cart tools
- Postgres schema and seed data
- Kestra workflow execution for post-order merchant automation

The app is designed to work locally even before you install optional Python agent packages. If `langgraph` is installed, the agent uses `StateGraph`; otherwise it runs the same graph path through a deterministic fallback for demos.

## Quick Start

```bash
npm start
```

Open http://localhost:3000 and try:

```text
Find waterproof trail shoes under $150
Add the best option to my cart
Checkout with standard shipping
```

## Optional Platform Services

Start Postgres and Kestra:

```bash
docker compose up -d
```

- Postgres: `localhost:5432`
- Kestra UI: http://localhost:8080
- Flow file: `kestra/flows/chat-commerce-order-fulfillment.yml`

Kestra is intentionally post-checkout. Shopify owns checkout, payment, tax, and order creation. After a Shopify order-paid event, the demo calls Kestra's execution API:

```text
POST /api/v1/main/executions/demo.commerce/chat-commerce-order-fulfillment
```

If Kestra is not running or the flow has not been imported yet, the chat still completes and reports that Kestra is configured but unavailable.

## Shopify Storefront MCP

Set a Shopify store domain to use Shopify's real Storefront MCP endpoint instead of the local demo catalog:

```bash
SHOPIFY_STORE_DOMAIN=thekohawkshop.com npm start
```

The MCP endpoint is:

```text
https://thekohawkshop.com/api/mcp
```

The agent calls Shopify's Storefront MCP tools for product search and cart updates, then sends the buyer to Shopify checkout. The "Simulate order paid" action represents a Shopify webhook and triggers Kestra post-order automation. Some Shopify stores restrict MCP access, so test against the specific store you plan to demo.

## Agent Demo From Terminal

```bash
npm run agent:demo
```

## Project Shape

```text
server.js                         NodeJS web/API server
public/                           Browser chat experience
agent/commerce_agent.py           LangGraph agent entry point
agent/mcp/commerce_mcp_server.py  Local + Shopify Storefront MCP adapter
data/catalog.json                 Demo catalog
db/init/001_schema.sql            Postgres schema and seed data
kestra/flows/                     Fulfillment workflow definitions
```

## Where To Extend

- Swap deterministic classification in `agent/commerce_agent.py` with an LLM planner.
- Point local MCP tools at Postgres by using `DATABASE_URL` and `psycopg`.
- Persist chat session cart IDs so Shopify cart state survives across turns.
- Add customer identity, promotions, returns, recommendations, and payment-provider mocks.
