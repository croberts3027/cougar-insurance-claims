---
description: Show a table's columns, joins and a sample of rows from the claims database
argument-hint: <table name, e.g. header>
---

Explore the table `$ARGUMENTS` in the claims database.

1. If `$ARGUMENTS` is not one of the 13 tables (`header`, `exposures`, `coverages`, `money`, `activities`, `notes`, `vehicles`, `incidents`, `contact_roles`, `negotiations`, `matters`, `users`, `change_log`), list them and ask which one the student wants.
2. Read that table's section in `docs/data-dictionary.md` (sections 5 and 6). Summarize what one row is, the primary key, how the table joins to others, and any gotchas (quoted columns, NULL meanings).
3. Use the student's language (Python or R; ask if unclear). Write a short script that uses the repo helpers (see `examples/`) and prints:
   - the row count,
   - 5 sample rows (use `LIMIT 5`; for `change_log`, `notes` and `activities` select only a few columns),
   - the NULL count per column, computed in one SQL aggregate as `COUNT(*) - COUNT(col)`.
4. Run it and report in plain language. Do not save the script unless the student asks.
