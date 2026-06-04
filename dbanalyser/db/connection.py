"""
DBAnalyser — PostgreSQL connection manager.
Uses a simple connection pool via psycopg2 + context manager.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Generator, Optional

import psycopg2
import psycopg2.extras
import psycopg2.pool

from dbanalyser.config import PostgresConfig

_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None
_lock = threading.Lock()


def init_pool(cfg: PostgresConfig, minconn: int = 1, maxconn: int = 10) -> None:
    """Initialise the global connection pool. Call once at startup."""
    global _pool
    with _lock:
        if _pool is None:
            _pool = psycopg2.pool.ThreadedConnectionPool(
                minconn, maxconn,
                host=cfg.host,
                port=cfg.port,
                dbname=cfg.database,
                user=cfg.user,
                password=cfg.password,
                options=f"-c search_path={cfg.db_schema},public",
            )


def close_pool() -> None:
    global _pool
    with _lock:
        if _pool:
            _pool.closeall()
            _pool = None


def _ensure_pool() -> None:
    """Lazily re-initialise the pool if it was lost (e.g. startup failure).
    Attempts to load config via the running API app; no-op if unavailable.
    NOTE: do NOT hold _lock here — init_pool acquires _lock internally."""
    if _pool is not None:
        return
    try:
        from dbanalyser.api.main import _get_cfg  # type: ignore
        cfg = _get_cfg()
        init_pool(cfg.postgres)
        import logging
        logging.getLogger("dbanalyser.api").info(
            "PostgreSQL pool lazily reinitialised."
        )
    except Exception as exc:
        raise RuntimeError(
            f"Connection pool not initialised and lazy reinit failed: {exc}"
        ) from exc


@contextmanager
def get_conn() -> Generator[psycopg2.extensions.connection, None, None]:
    """Yield a connection from the pool; return it on exit."""
    _ensure_pool()
    if _pool is None:
        raise RuntimeError("Connection pool not initialised. Call init_pool() first.")
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


@contextmanager
def get_cursor(conn=None) -> Generator[psycopg2.extensions.cursor, None, None]:
    """Yield a RealDictCursor. If conn is provided use it, else borrow from pool."""
    if conn is not None:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield cur
        finally:
            cur.close()
    else:
        with get_conn() as c:
            cur = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            try:
                yield cur
            finally:
                cur.close()


def test_connection(cfg: PostgresConfig) -> tuple[bool, str]:
    """Return (ok, message). Used by `dbanalyser validate`."""
    try:
        conn = psycopg2.connect(
            host=cfg.host, port=cfg.port,
            dbname=cfg.database, user=cfg.user, password=cfg.password,
            connect_timeout=5,
        )
        conn.close()
        return True, f"Connected to {cfg.host}:{cfg.port}/{cfg.database}"
    except Exception as exc:
        return False, str(exc)


def create_schema(cfg: PostgresConfig, schema_sql_path: str) -> None:
    """Execute schema.sql against the target database."""
    import pathlib
    sql = pathlib.Path(schema_sql_path).read_text(encoding="utf-8")
    conn = psycopg2.connect(
        host=cfg.host, port=cfg.port,
        dbname=cfg.database, user=cfg.user, password=cfg.password,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    finally:
        conn.close()
