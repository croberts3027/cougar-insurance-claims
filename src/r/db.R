# Connect to the Neon claims database.
#
# Connection settings are the standard PostgreSQL variables PGHOST, PGDATABASE, PGUSER,
# PGPASSWORD and PGSSLMODE, read from the `.env` file in the repo root (see `.env.example`).
#
#   source(here::here("src/r/db.R"))
#   df <- query("SELECT COUNT(*) AS claims FROM header")
#   df <- query(read_sql("00_smoke_test.sql"))     # run a file from sql/
#   con <- get_con()                                # or keep one connection open yourself;
#   DBI::dbDisconnect(con)                          # remember to disconnect

.required_vars <- c("PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD")

get_con <- function() {
  readRenviron(here::here(".env"))
  missing <- .required_vars[Sys.getenv(.required_vars) == ""]
  if (length(missing)) {
    stop(
      "Missing ", paste(missing, collapse = ", "), ". Copy .env.example to .env and fill in ",
      "the values from your instructor (see docs/getting-started.md).",
      call. = FALSE
    )
  }
  # No arguments: RPostgres reads the PG* environment variables.
  DBI::dbConnect(RPostgres::Postgres())
}

# Run a query on a short-lived connection and return a data frame.
# Use $1, $2 placeholders with `params`, e.g. query("... WHERE claim_id = $1", list(900001)).
query <- function(sql, params = NULL) {
  con <- get_con()
  on.exit(DBI::dbDisconnect(con))
  DBI::dbGetQuery(con, sql, params = params)
}

# Return the text of a file in the repo's sql/ folder, e.g. read_sql("00_smoke_test.sql").
read_sql <- function(name) {
  paste(readLines(here::here("sql", name), warn = FALSE), collapse = "\n")
}
