"""Connect to the Neon claims database.

Connection settings are the standard PostgreSQL variables PGHOST, PGDATABASE, PGUSER,
PGPASSWORD and PGSSLMODE, read from the `.env` file in the repo root (see `.env.example`).

    from cougar_claims.db import query, read_sql
    df = query("SELECT COUNT(*) AS claims FROM header")
    df = query(read_sql("00_smoke_test.sql"))       # run a file from sql/
    df = query("SELECT * FROM header WHERE claim_id = :id", {"id": 900001})
"""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

REPO_ROOT = Path(__file__).resolve().parents[3]
_REQUIRED = ("PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD")
_engine: Engine | None = None


def get_engine() -> Engine:
    """Return a shared SQLAlchemy engine, creating it on first use."""
    global _engine
    if _engine is None:
        load_dotenv(REPO_ROOT / ".env")
        missing = [name for name in _REQUIRED if not os.environ.get(name)]
        if missing:
            raise RuntimeError(
                f"Missing {', '.join(missing)}. Copy .env.example to .env and fill in "
                "the values from your instructor (see docs/getting-started.md)."
            )
        # No host/user in the URL: psycopg reads the PG* environment variables.
        # pool_pre_ping reconnects if Neon suspended the compute while idle.
        _engine = create_engine("postgresql+psycopg://", pool_pre_ping=True)
    return _engine


def query(sql: str, params: dict | None = None) -> pd.DataFrame:
    """Run a SQL query and return the result as a DataFrame. Use :name placeholders for params."""
    try:
        conn = get_engine().connect()
    except OperationalError as err:
        # Replace the long SQLAlchemy traceback with the one line a student needs.
        reason = str(err.orig).splitlines()[0]
        raise RuntimeError(
            f"Could not connect to the database: {reason}\n"
            "Check the values in .env (see docs/getting-started.md)."
        ) from None
    with conn:
        return pd.read_sql_query(text(sql), conn, params=params)


def read_sql(name: str) -> str:
    """Return the text of a file in the repo's sql/ folder, e.g. read_sql("00_smoke_test.sql")."""
    return (REPO_ROOT / "sql" / name).read_text(encoding="utf-8")
