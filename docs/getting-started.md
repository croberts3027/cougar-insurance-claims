# Getting Started

About 20 minutes, once. You need Git, and either Python 3.11+ or R 4.1+ (or both).

## 1. Get your own copy of the repo

The course repo is private. Your instructor adds you as a collaborator: accept the invitation email from GitHub first.

**Fork (default).** On GitHub, click **Fork**, then clone your fork:

```bash
git clone https://github.com/<your-username>/cougar-insurance-claims.git
cd cougar-insurance-claims
```

**Branch (if your instructor asks for it).** Clone the course repo, then make a branch named after you:

```bash
git switch -c yourname-project
```

To pick up course updates on a fork, open your fork on GitHub and click **Sync fork**, then run `git pull`.

## 2. Add your database login

Your instructor gives you a host, user and password for a read-only database login.

```powershell
# PowerShell
Copy-Item .env.example .env
```

```bash
# bash / zsh
cp .env.example .env
```

Open `.env` in an editor and replace the placeholder values. Keep `PGDATABASE=neondb` and `PGSSLMODE=require`.

> **Never commit `.env`, paste it into a chat, or post it in an issue.** It is gitignored, but run `git status` before every commit and check that `.env` is not listed. If you ever commit it by mistake, tell your instructor right away.

## 3. Set up your language

### Python

```powershell
# PowerShell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

```bash
# bash / zsh
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

`pip install -e .` installs the libraries and the `cougar_claims` helper package. In VS Code, pick the `.venv` interpreter for notebooks.

### R

From the repo root, in R or RStudio:

```r
source("src/r/install_packages.R")
```

## 4. Check that it works

From the repo root:

```bash
python examples/python/01_connect.py
Rscript examples/r/01_connect.R
```

Run the one for your language. You should see `header has 20,000 claims` and a list of 13 tables. The first query after a quiet period can take a few seconds: the database sleeps when idle and wakes up on demand.

| Error | Fix |
| --- | --- |
| `Missing PGHOST, ...` | `.env` is missing or still has no values. Re-do step 2. |
| `password authentication failed` | Typo in `PGUSER` or `PGPASSWORD`. Ask your instructor to confirm them. |
| `SSL` or `connection refused` errors | Make sure `PGSSLMODE=require` is in `.env` and you are not on a network that blocks Postgres (port 5432). |
| `pip install` fails with `OSError: [Errno 2] No such file or directory` and a very long path ending in `.pyi` | Windows path too long. Clone the repo into a short folder such as `C:\code\cougar-insurance-claims`, or turn on Windows long-path support. |

## 5. Learn the data, then run the other examples

1. Read [claims-primer.md](claims-primer.md) for the business background and [data-dictionary.md](data-dictionary.md) for every table and column.
2. Run `02_query_to_dataframe` and `03_join_claims_exposures` (in `examples/python/` or `examples/r/`). `02` should print a total indemnity paid of `$138,789,173.80`. If your own query for this number differs, a filter is wrong.
3. Put your own SQL in `sql/` and your work in `notebooks/`, `src/` and `reports/`. In your own code, import the helpers instead of writing connection code:

```python
from cougar_claims.db import query, read_sql
df = query("SELECT claim_id, lob FROM header LIMIT 5")
```

```r
source(here::here("src/r/db.R"))
df <- query("SELECT claim_id, lob FROM header LIMIT 5")
```

## Document your work with a Quarto website

This repo is a [Quarto](https://quarto.org) website. Your pages in `notebooks/` become site pages, next to a home page, a project plan and a weekly log. It works with Python or R.

1. Install Quarto from [quarto.org/docs/get-started](https://quarto.org/docs/get-started/) and check it with `quarto --version`.
2. Open `index.qmd`, `project-plan.qmd` and `weekly-log.qmd` and replace the TODO text.
3. Start an analysis page by copying the starter for **your** language (or run `/new-analysis` in Claude Code). Only copy one language per page, and do not copy the R starter if you do not have R:

   ```powershell
   Copy-Item templates/starter-python.qmd notebooks/01_first-analysis.qmd
   Copy-Item templates/starter-r.qmd notebooks/01_first-analysis.qmd
   ```

4. Preview the site while you work. Run this from the repo root, with your Python virtual environment active:

   ```bash
   quarto preview
   ```

5. Publish when you are ready, to [Posit Connect Cloud](https://connect.posit.cloud). Create an account there first. Your published site is public by default; restricting who can view it needs a paid plan. Pick one way:
   - **From GitHub** (the site updates each time you push):
     1. Render the site on your computer, then commit and push the result:

        ```bash
        quarto render
        git add -A
        git commit -m "Render site"
        git push
        ```

        This saves your results in `_freeze/`. Connect Cloud reuses them: it does not run your code or connect to the database, so it needs no password. Python uses the `requirements.txt` already in the repo root. R needs a `renv.lock` or `manifest.json` that you create.
     2. In Connect Cloud, click **Publish**, then **Quarto**. Choose your repo and branch, and set **Primary file** to `_quarto.yml`.
     3. Leave **Automatically publish on push** on, then click **Publish**.

     Each time you change the code in a page, run `quarto render` again and push `_freeze/` with it. If you push changed code without the new `_freeze/`, Connect Cloud tries to run the page, and the build fails because it has no `cougar_claims` package or database login.

     On a free Connect Cloud account this only works for a public repo. The course repo is private, so your fork is private too: use the next option, or ask your instructor.
   - **From your computer** (works with a private repo): run `quarto publish posit-connect-cloud` from the repo root. It needs Quarto 1.9 or newer (`quarto --version`). Quarto renders the site on your machine, using your `.env`, and uploads the result. The first time, your browser opens so you can authorize access. It writes `_publish.yml`, which you can commit; it holds no password.

Commit the `_freeze/` folder, which stores your saved results so a page is not re-run unless it changes. Do not commit `_site/`; it is gitignored.

If Quarto cannot find Python or Jupyter, activate your virtual environment in the same terminal, or set `QUARTO_PYTHON` to the full path of `.venv\Scripts\python.exe`.

## Use Claude Code

This repo is set up for [Claude Code](https://claude.com/claude-code). From the repo root, run `claude`. It reads `CLAUDE.md` for the course context, the data gotchas and the rules about your database login.

- `/explore-table header` shows the columns of a table from the data dictionary and a sample of rows.
- `/new-analysis` starts a new script or notebook with the as-of date and a leakage checklist.
- Claude is set up not to read `.env`. Do not paste your password into the chat.

## Where your files go

| You are making | Put it in |
| --- | --- |
| Analysis page (Quarto `.qmd`) or script | `notebooks/` |
| Home page, project plan, weekly log | `index.qmd`, `project-plan.qmd`, `weekly-log.qmd` |
| Reusable functions | `src/python/` or `src/r/` |
| Local data extracts (not committed) | `data/raw/`, `data/interim/`, `data/processed/` |
| Charts for your report | `reports/figures/` |
| Saved models (not committed) | `models/` |
