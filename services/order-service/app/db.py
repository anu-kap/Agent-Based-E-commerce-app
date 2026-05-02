"""Postgres helpers — gracefully optional when DATABASE_URL is unset."""
import json
import os
from pathlib import Path
from typing import Any

def _find_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "db" / "init").exists():
            return parent
    return here.parents[1]  # Docker fallback: /app

ROOT = _find_root()
SCHEMA_PATH = ROOT / "db" / "init" / "001_schema.sql"

_disabled = False
_initialized = False


def _connect():
    global _disabled
    if _disabled:
        return None
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        return None
    try:
        import psycopg
    except ImportError:
        _disabled = True
        return None
    try:
        return psycopg.connect(url, connect_timeout=3)
    except Exception:
        _disabled = True
        return None


def _ensure_schema(conn) -> None:
    global _initialized
    if _initialized:
        return
    if SCHEMA_PATH.exists():
        with conn.cursor() as cur:
            cur.execute(SCHEMA_PATH.read_text())
        conn.commit()
    _initialized = True


def save_order(order: dict[str, Any], session_id: str = "demo") -> None:
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
            cur.execute("INSERT INTO chat_sessions (id) VALUES (%s) ON CONFLICT (id) DO NOTHING", (session_id,))
            cur.execute(
                "INSERT INTO orders (id, session_id, status, total, payload) VALUES (%s, %s, %s, %s, %s::jsonb) ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status, total = EXCLUDED.total, payload = EXCLUDED.payload",
                (order_id, session_id, status, total, json.dumps(order)),
            )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()
