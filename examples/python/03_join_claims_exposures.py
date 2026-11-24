"""Two ways to combine tables: a join in SQL, and a join in pandas.

Run from the repo root:  python examples/python/03_join_claims_exposures.py

Gotchas shown here (full list: docs/data-dictionary.md, section 4):
- exposures."SegmentName" has capital letters, so it must be double-quoted in SQL.
- The database has no foreign keys. claim_id is the join key for almost every table.
"""

from cougar_claims.db import query, read_sql

# 1. Join in SQL: one claim's exposures with their coverage limits (sql/02_claim_exposures.sql).
print(query(read_sql("02_claim_exposures.sql")))

# 2. Join in pandas: pull two small tables, then merge them on claim_id.
claims = query("SELECT claim_id, lob, claim_state FROM header")
exposures = query(
    'SELECT exposure_pk, claim_id, exposure_type, "SegmentName" AS segment, paid_to_date FROM exposures'
)
merged = claims.merge(exposures, on="claim_id", how="left")

summary = (
    merged.groupby("segment")["paid_to_date"]
    .agg(exposures="count", paid="sum")
    .sort_values("paid", ascending=False)
)
print(summary)
