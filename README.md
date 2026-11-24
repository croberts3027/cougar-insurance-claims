# Cougar Insurance Claims

Course repo for the Applied Data Science Practicum on claims analytics. You will analyze 20,000 **synthetic** (fake) auto and homeowner insurance claims stored in a Neon Postgres database. Use **Python or R**, whichever you prefer.

## Quickstart

1. **Fork** this repo on GitHub, then clone your fork. (Your instructor may instead ask you to create a branch.)
2. **Get your database login** from your instructor. Copy `.env.example` to `.env` and fill it in. `.env` is gitignored: never commit or share it.
3. **Set up your language** (details in [docs/getting-started.md](docs/getting-started.md)):
   - Python 3.11+: `python -m venv .venv`, activate it, then `pip install -e .`
   - R 4.1+: `source("src/r/install_packages.R")`
4. **Run the first example** from the repo root. It should report 20,000 claims.
   - Python: `python examples/python/01_connect.py`
   - R: `Rscript examples/r/01_connect.R`
5. **Read the docs** below before you write queries.
6. **Do your work** in `notebooks/`, `src/` and `reports/`, on your own fork or branch, and document it on your Quarto website.

## What is where

| Path | What it holds |
| --- | --- |
| `docs/` | Syllabus, [claims primer](docs/claims-primer.md), [data dictionary](docs/data-dictionary.md), [getting started](docs/getting-started.md) |
| `sql/` | Example SQL files that work in any language |
| `examples/python/`, `examples/r/` | The same three examples in each language: connect, query to a data frame, join tables |
| `src/python/cougar_claims/`, `src/r/` | Connection helpers (`query()`, `read_sql()`) and reusable code |
| `notebooks/` | Your analysis pages, written as Quarto (`.qmd`) notebooks |
| `index.qmd`, `project-plan.qmd`, `weekly-log.qmd`, `_quarto.yml` | Your project website ([how to use it](docs/getting-started.md#document-your-work-with-a-quarto-website)) |
| `templates/` | Starter `.qmd` pages, one for Python and one for R |
| `data/` | Local data you create (`raw`, `interim`, `processed`). Contents are gitignored |
| `reports/figures/`, `models/` | Charts for your report; saved models (model files are gitignored) |
| `CLAUDE.md`, `.claude/` | Claude Code setup (see [getting started](docs/getting-started.md#use-claude-code)) |

## Rules that protect you

- The data is in Neon, not in this repo. Query it; do not download copies into git.
- Never commit `.env`.
- Use `docs/data-dictionary.md` section 4 before you join tables. The database has no foreign keys.
- Follow the [AI use policy](docs/ai-policy.md): AI tutors you, it does not do the project for you. Log your AI use in `weekly-log.qmd`.

Instructor: see [docs/instructor-setup.md](docs/instructor-setup.md).
