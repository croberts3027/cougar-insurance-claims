# Two ways to combine tables: a join in SQL, and a join in dplyr.
# Run from the repo root:  Rscript examples/r/03_join_claims_exposures.R
#
# Gotchas shown here (full list: docs/data-dictionary.md, section 4):
# - exposures."SegmentName" has capital letters, so it must be double-quoted in SQL.
# - The database has no foreign keys. claim_id is the join key for almost every table.
# Needs R 4.1 or newer for the |> pipe.

library(dplyr)
source(here::here("src/r/db.R"))

# 1. Join in SQL: one claim's exposures with their coverage limits (sql/02_claim_exposures.sql).
print(query(read_sql("02_claim_exposures.sql")))

# 2. Join in dplyr: pull two small tables, then join them on claim_id.
claims <- query("SELECT claim_id, lob, claim_state FROM header")
exposures <- query(
  'SELECT exposure_pk, claim_id, exposure_type, "SegmentName" AS segment, paid_to_date FROM exposures'
)

left_join(claims, exposures, by = "claim_id") |>
  group_by(segment) |>
  summarise(exposures = n(), paid = sum(paid_to_date)) |>
  arrange(desc(paid)) |>
  print()
