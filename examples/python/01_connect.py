"""Connect to the claims database and run a smoke test.

Run from the repo root:  python examples/python/01_connect.py
"""

from cougar_claims.db import query, read_sql

claims = query(read_sql("00_smoke_test.sql"))
print(f"Connected. header has {claims['claims'].iloc[0]:,} claims (expected 20,000).")

tables = query(
    """
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'public' ORDER BY table_name
    """
)
print("Tables:", ", ".join(tables["table_name"]))
