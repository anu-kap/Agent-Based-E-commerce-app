-- Storefront Concierge schema.
-- Idempotent: safe to run on every app start.
--
-- Postgres in this project is BOTH a cache (products_cache) and a
-- persistence layer (chat_sessions, chat_intents, orders). Live product
-- data still comes from Shopify Storefront MCP; we cache responses here
-- to absorb hiccups and reduce latency.

-- Cache of Shopify catalog search responses keyed by normalized query.
CREATE TABLE IF NOT EXISTS products_cache (
  query_key   TEXT PRIMARY KEY,
  response    JSONB NOT NULL,
  fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per chat session id minted by the browser (or "demo" for the CLI).
CREATE TABLE IF NOT EXISTS chat_sessions (
  id          TEXT PRIMARY KEY,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Every shopper turn — feeds the Campus Demand Radar's intent signal.
CREATE TABLE IF NOT EXISTS chat_intents (
  id            BIGSERIAL PRIMARY KEY,
  session_id    TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
  message       TEXT NOT NULL,
  selected_sku  TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS chat_intents_recent_idx
  ON chat_intents(created_at DESC);

-- Local demo orders. Real Shopify orders live in Shopify; we persist
-- the demo path so the radar/automation can replay against them later.
CREATE TABLE IF NOT EXISTS orders (
  id          TEXT PRIMARY KEY,
  session_id  TEXT REFERENCES chat_sessions(id),
  status      TEXT NOT NULL,
  total       NUMERIC(10, 2) NOT NULL,
  payload     JSONB NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
