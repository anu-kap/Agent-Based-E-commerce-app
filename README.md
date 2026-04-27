# Agentic Commerce Chat

A demoable chat-based ecommerce experience using:

- NodeJS for the web server and chat API
- Python with LangGraph-style agent orchestration
- MCP-style JSON-RPC commerce tools for catalog search, cart quote, and order creation
- Postgres schema and seed data
- Kestra workflow definition for fulfillment orchestration

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

## Agent Demo From Terminal

```bash
npm run agent:demo
```

## Project Shape

```text
server.js                         NodeJS web/API server
public/                           Browser chat experience
agent/commerce_agent.py           LangGraph agent entry point
agent/mcp/commerce_mcp_server.py  MCP-style JSON-RPC tool server
data/catalog.json                 Demo catalog
db/init/001_schema.sql            Postgres schema and seed data
kestra/flows/                     Fulfillment workflow definitions
```

## Where To Extend

- Swap deterministic classification in `agent/commerce_agent.py` with an LLM planner.
- Point MCP tools at Postgres by using `DATABASE_URL` and `psycopg`.
- Trigger Kestra through its API after `create_order`.
- Add customer identity, promotions, returns, recommendations, and payment-provider mocks.
