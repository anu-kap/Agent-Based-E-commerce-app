"""Postgres helpers for Storefront Concierge.

Postgres is optional. If DATABASE_URL is unset or unreachable, every
function in this module silently no-ops (or returns an empty result).
The chat path keeps working with no DB at all — Postgres only adds
caching of Shopify responses and persistence of session/intent/order
history.

Schema is auto-bootstrapped from db/init/001_schema.sql on first call;
all DDL is idempotent.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "db" / "init" / "001_schema.sql"

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
_initialized = False
_disabled = False  # set True on the first connection failure to avoid retry storms


def is_enabled() -> bool:
    return bool(DATABASE_URL) and not _disabled


def _connect():
    """Open a short-lived connection. Returns None if unavailable."""
    global _disabled
    if not is_enabled():
        return None
    try:
        import psycopg
    except ImportError:
        _disabled = True
        return None
    try:
        return psycopg.connect(DATABASE_URL, connect_timeout=3)
    except Exception:
        _disabled = True
        return None


def _ensure_schema(conn) -> None:
    global _initialized
    if _initialized:
        return
    with conn.cursor() as cur:
        cur.execute(SCHEMA_PATH.read_text())
    conn.commit()
    _initialized = True


def log_intent(session_id: str, message: str, selected_sku: str = "") -> None:
    if not session_id or not message:
        return
    conn = _connect()
    if conn is None:
        return
    try:
        _ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_sessions (id) VALUES (%s) ON CONFLICT (id) DO NOTHING",
                (session_id,),
            )
            cur.execute(
                "INSERT INTO chat_intents (session_id, message, selected_sku) VALUES (%s, %s, %s)",
                (session_id, message, selected_sku or None),
            )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def recent_intents(limit: int = 15) -> List[Dict[str, Any]]:
    conn = _connect()
    if conn is None:
        return []
    try:
        _ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT session_id, message, COALESCE(selected_sku, ''), created_at
                FROM chat_intents
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
        return [
            {
                "sessionId": session_id,
                "message": message,
                "selectedSku": selected_sku,
                "timestamp": created_at.isoformat(),
            }
            for session_id, message, selected_sku, created_at in rows
        ]
    except Exception:
        return []
    finally:
        conn.close()


def cache_get(query_key: str, max_age_seconds: int = 3600) -> Tuple[Optional[Any], Optional[float]]:
    """Return (response, age_seconds) for a fresh cache hit, else (None, None).

    A "stale" entry (age > max_age_seconds) is NOT returned by this call.
    Use cache_get_stale for last-resort fallback when the live source fails.
    """
    response, age = _cache_lookup(query_key)
    if response is None or age is None:
        return None, None
    if age > max_age_seconds:
        return None, None
    return response, age


def cache_get_stale(query_key: str) -> Optional[Any]:
    """Return the latest cached response regardless of age, or None."""
    response, _ = _cache_lookup(query_key)
    return response


def _cache_lookup(query_key: str) -> Tuple[Optional[Any], Optional[float]]:
    conn = _connect()
    if conn is None:
        return None, None
    try:
        _ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT response, EXTRACT(EPOCH FROM (now() - fetched_at))
                FROM products_cache
                WHERE query_key = %s
                """,
                (query_key,),
            )
            row = cur.fetchone()
        if not row:
            return None, None
        response, age = row
        return response, float(age) if age is not None else None
    except Exception:
        return None, None
    finally:
        conn.close()


def cache_put(query_key: str, response: Any) -> None:
    if not query_key or response is None:
        return
    conn = _connect()
    if conn is None:
        return
    try:
        _ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO products_cache (query_key, response, fetched_at)
                VALUES (%s, %s::jsonb, now())
                ON CONFLICT (query_key) DO UPDATE
                  SET response = EXCLUDED.response,
                      fetched_at = EXCLUDED.fetched_at
                """,
                (query_key, json.dumps(response)),
            )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def save_order(order: Dict[str, Any], session_id: str = "demo") -> None:
    order_id = order.get("orderId") if isinstance(order, dict) else None
    if not order_id:
        return
    conn = _connect()
    if conn is None:
        return
    try:
        _ensure_schema(conn)
        quote = order.get("quote") or {}
        total = float(quote.get("total", 0) or 0)
        status = str(order.get("status", "created"))
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_sessions (id) VALUES (%s) ON CONFLICT (id) DO NOTHING",
                (session_id,),
            )
            cur.execute(
                """
                INSERT INTO orders (id, session_id, status, total, payload)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (id) DO UPDATE
                  SET status = EXCLUDED.status,
                      total = EXCLUDED.total,
                      payload = EXCLUDED.payload
                """,
                (order_id, session_id, status, total, json.dumps(order)),
            )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()
