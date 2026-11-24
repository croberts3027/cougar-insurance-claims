# Run a SQL file and work with the result as a data frame.
# Run from the repo root:  Rscript examples/r/02_query_to_dataframe.R
# The check value for total indemnity paid is in docs/claims-primer.md.

source(here::here("src/r/db.R"))

paid <- query(read_sql("01_claims_overview.sql"))

print(head(paid))
cat(sprintf("Claims with indemnity payments: %s\n", format(nrow(paid), big.mark = ",")))
cat(sprintf("Total indemnity paid: $%s  (expected $138,789,173.80)\n",
            formatC(sum(paid$indemnity_paid), format = "f", digits = 2, big.mark = ",")))

