"""Run a SQL file and work with the result as a pandas DataFrame.

Run from the repo root:  python examples/python/02_query_to_dataframe.py
The check value for total indemnity paid is in docs/claims-primer.md.
"""

from cougar_claims.db import query, read_sql

paid = query(read_sql("01_claims_overview.sql"))

print(paid.head())
print(f"Claims with indemnity payments: {len(paid):,}")
print(f"Total indemnity paid: ${paid['indemnity_paid'].sum():,.2f}  (expected $138,789,173.80)")
