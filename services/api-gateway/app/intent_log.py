"""Intent logging + retrieval — optional, gracefully disabled without DATABASE_URL."""
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
_in_memory: list[dict[str, Any]] = []
MAX_MEMORY = 60


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


def log_intent(session_id: str, message: str, selected_sku: str = "") -> None:
    global _in_memory
    entry = {"sessionId": session_id, "message": message, "selectedSku": selected_sku}
    _in_memory = ([entry] + _in_memory)[:MAX_MEMORY]

    conn = _connect()
    if conn is None:
        return
    try:
        _ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute("INSERT INTO chat_sessions (id) VALUES (%s) ON CONFLICT (id) DO NOTHING", (session_id,))
            cur.execute("INSERT INTO chat_intents (session_id, message, selected_sku) VALUES (%s, %s, %s)", (session_id, message, selected_sku or None))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def recent_intents(limit: int = 15) -> list[dict[str, Any]]:
    conn = _connect()
    if conn is None:
        return _in_memory[:limit]
    try:
        _ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT session_id, message, COALESCE(selected_sku, ''), created_at FROM chat_intents ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()
        return [{"sessionId": sid, "message": msg, "selectedSku": sku, "timestamp": ts.isoformat()} for sid, msg, sku, ts in rows]
    except Exception:
        return _in_memory[:limit]
    finally:
        conn.close()
