# Instructor Setup

One-time steps before you share the repo with students. Students do not need this page.

## 1. Create the read-only database role

In the Neon SQL editor, as the project owner, run the following. Create the role with SQL, not through the Neon console: console-created roles get extra privileges.

```sql
CREATE ROLE student_ro WITH LOGIN PASSWORD '<generate a strong password>';
GRANT CONNECT ON DATABASE neondb TO student_ro;
GRANT USAGE ON SCHEMA public TO student_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO student_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO student_ro;

-- Optional guards for a shared compute:
ALTER ROLE student_ro SET statement_timeout = '60s';
ALTER ROLE student_ro CONNECTION LIMIT 20;
```

Give students the host, the user (`student_ro`) and the password in class or through your LMS. Do not post them in the repo, an issue or a public channel.

Use the **direct** (non-pooled) Neon host unless you have a reason not to.

## 2. Check storage, then add indexes

The database is about 467 MB. Check your Neon plan's storage limit in the Neon console **before** adding indexes: they add size, and you may hit the cap.

The tables have primary keys only. A filter on `claim_id` in a big table (`change_log`, `activities`, `notes`) scans the whole table. For repeated use, run as the owner, for example:

```sql
CREATE INDEX ON change_log (claim_id);
```

A read-only student role cannot create indexes.

## 3. Test it yourself

Create `.env` from `.env.example` with the student role, then run the first two examples in each language. `02_query_to_dataframe` must print `$138,789,173.80`.

## 4. Make the repo private for the class

- Confirm no `.env`, CSV or other data file is committed: `git status`.
- **Make the repo private before any student forks or branches it.** Forks made while the repo is public stay public after you switch it to private.
- Add each student as a collaborator (Settings > Collaborators). To let them fork, turn on Settings > General > Allow forking; forks of a private repo are private. Otherwise they work on a branch, which needs write access.
- **GitHub Pages and the student Quarto sites:** on a private repo, Pages needs GitHub Pro, Team or Enterprise Cloud. Students can get Pro free through the GitHub Student Developer Pack. A Pages site is public even when its repo is private (except on Enterprise Cloud), so ask students before they publish. `quarto publish quarto-pub` is a free alternative, and publishing is optional.

## 5. End of term

Rotate or drop the role so forks with a leaked `.env` stop working:

```sql
ALTER ROLE student_ro WITH PASSWORD '<new password>';
-- or: REASSIGN OWNED BY student_ro TO <owner>; DROP OWNED BY student_ro; DROP ROLE student_ro;
```
