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
- **Posit Connect Cloud and the student Quarto sites:** each student needs their own Connect Cloud account. Publishing from GitHub on a free account works only for public repos; private repos need a paid plan. Student forks of the private course repo are private, so free-account students should run `quarto publish posit-connect-cloud` from their own machine instead (Quarto 1.9 or newer). That route renders locally, so the `.env` password never leaves their computer. The GitHub route may need the `PG*` variables stored as secret variables in Connect Cloud, which puts the student role's password there. Published sites are public by default, so ask students before they publish. Publishing is optional.

## 5. End of term

Rotate or drop the role so forks with a leaked `.env` stop working:

```sql
ALTER ROLE student_ro WITH PASSWORD '<new password>';
-- or: REASSIGN OWNED BY student_ro TO <owner>; DROP OWNED BY student_ro; DROP ROLE student_ro;
```
