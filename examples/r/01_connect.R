# Connect to the claims database and run a smoke test.
# Run from the repo root:  Rscript examples/r/01_connect.R

source(here::here("src/r/db.R"))

claims <- query(read_sql("00_smoke_test.sql"))
cat(sprintf("Connected. header has %s claims (expected 20,000).\n",
            format(as.numeric(claims$claims), big.mark = ",")))

tables <- query(
  "SELECT table_name FROM information_schema.tables
   WHERE table_schema = 'public' ORDER BY table_name"
)
cat("Tables:", paste(tables$table_name, collapse = ", "), "\n")

