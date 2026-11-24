---
description: Start a new analysis script or notebook with the as-of date and a leakage checklist
argument-hint: <short-name, e.g. total-loss-baseline>
---

Create a new analysis called `$ARGUMENTS`.

1. If unclear, ask whether the student uses Python or R. Use a Quarto page (`.qmd`) unless they ask for a plain script (`.py` or `.R`).
2. Create `notebooks/NN_$ARGUMENTS.qmd`, where `NN` is the next two-digit number after the files already in `notebooks/` (start at `01`). Copy `templates/starter-python.qmd` or `templates/starter-r.qmd` and set `title:` and `description:` in its front matter so the page shows up on the site's Analyses page. Do not mix languages in one page.
3. Make sure it imports the repo's database helpers (see `examples/`), defines `AS_OF = "2026-10-07 12:00:00"` (the data is frozen at this moment; never use `now()`), and has these section headings: Question, Target and scoring point, Data pull, Features, Leakage check, Results. The starter already has them.
4. Under "Leakage check", add this checklist:
   - [ ] Every feature is known at the scoring point (usually first notice of loss).
   - [ ] No notes written after the scoring point are used.
   - [ ] `damage_severity`, `total_loss` and `damage_description` are not used as first-notice features.
   - [ ] Split by loss date: train 2024, validate Jan-Jun 2025, test Jul-Dec 2025.
   - [ ] Open claims (about 7%) are handled, since recent claims are immature.
5. Leave each section as a TODO. Do not write the analysis. Tell the student what to do next.
