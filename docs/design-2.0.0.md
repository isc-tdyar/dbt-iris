# dbt-iris 2.0.0: what changed from 1.9.x, and why

This note is for the maintainers of dbt-iris. It sets out where 2.0.0 does something differently
from 1.9.x, why, what that costs, and which crashes in the official InterSystems driver are still
possible. It goes with the stacked branches on
[isc-tdyar/dbt-iris](https://github.com/isc-tdyar/dbt-iris), from `pr/driver-and-packaging` to
`pr/guide`.

Everything below was measured on public IRIS Community builds, 2026.1.0.234 (`latest-em`),
2026.2.0.221 (`latest-cd`) and 2026.3.0L.196 (`latest-preview`), with `intersystems-irispython`
5.4.1, dbt-core 1.11 and 1.12, and Python 3.10 to 3.12. On each build the full suite passes apart
from one deliberate expected failure that records an IRIS defect.

## At a glance

| Area                                      | 1.9.x                                                                                                   | 2.0.0                                                                                                                                                              | Why                                                                                                                                             |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| Driver                                    | Bundled `intersystems_iris` 3.9.3 (pure Python); `driver` setting chose bundled, official or SQLAlchemy | Official `intersystems-irispython` 5.4 or later only                                                                                                               | The 3.9.3 download URL returns 404, so the bundled driver can no longer be built. It speaks xDBC protocol 65, so IRIS refuses some CTEs (below) |
| Packaging                                 | The wheel also carried `iris`, `intersystems_iris` and `irisnative`                                     | Only the `dbt` packages                                                                                                                                            | Installing 1.9.x replaced the official driver's `iris/__init__.py`, and uninstalling it deleted the file                                        |
| CTEs                                      | The bundled driver rewrote most CTEs into subqueries on the client                                      | The adapter moves CTEs to where IRIS accepts them (below)                                                                                                          | Same coverage, on the server's own CTE support, and CTEs with a column list now work                                                            |
| `merge`                                   | `INSERT OR UPDATE`                                                                                      | `UPDATE ... FROM` plus `INSERT ... WHERE NOT EXISTS`; `MERGE` when the server accepts it                                                                           | `INSERT OR UPDATE` matches on a primary key or unique index. Tables dbt builds have neither, so updated rows were added again                   |
| `delete+insert`                           | `IFNULL(key, '') IN (...)`                                                                              | Null-safe `EXISTS`                                                                                                                                                 | For integer keys the `IN` matched nothing, so every run added duplicates                                                                        |
| `insert_overwrite`                        | Offered; the macro was an upsert                                                                        | Removed                                                                                                                                                            | The name promised an overwrite; `merge` does what the macro did                                                                                 |
| `microbatch`                              | Not offered                                                                                             | New                                                                                                                                                                |                                                                                                                                                 |
| Snapshot `HASH()`                         | `LANGUAGE PYTHON` SQL function                                                                          | ObjectScript SQL function, same values (including `''`, hashed as `$c(0)`)                                                                                         | No Embedded Python needed; existing `dbt_scd_id` values stay valid                                                                              |
| Snapshots                                 | Snapshot macros from before dbt 1.9                                                                     | dbt 1.9 configuration (`hard_deletes`, multi-column keys, `snapshot_meta_column_names`, `dbt_valid_to_current`); snapshot time read once per run with microseconds | Two runs in one second gave a changed row its predecessor's `dbt_scd_id`                                                                        |
| Python models                             | Lines starting with `#` deleted; code inlined into the procedure body                                   | Code passed base64-encoded and run with `exec`                                                                                                                     | IRIS re-indents a `LANGUAGE PYTHON` body, which broke multi-line strings, and the `#` rule deleted lines inside strings                         |
| Temporary and backup tables               | Fixed suffixes                                                                                          | Invocation id in every name; temporary and staging tables dropped when the model is done                                                                           | Overlapping runs shared one table (issue #3)                                                                                                    |
| `materialized_view`                       | Not supported                                                                                           | Built as a table rebuilt on every run, or as a view (`iris_materialized_view_as`)                                                                                  | Projects written for other warehouses run unchanged                                                                                             |
| Row comparison (`get_rows_different_sql`) | `SELECT 0,0`                                                                                            | Real comparison, normalised per column type                                                                                                                        | dbt's equality checks could never fail, so no test compared table contents                                                                      |
| Requirements                              | dbt-core 1.8 or later, Python above 3.7                                                                 | dbt-core 1.10 or later (dbt-adapters 1.15.2), Python 3.10 or later                                                                                                 | The floor 2.0.0 is built on; CI tests dbt-core 1.11 and 1.12                                                                                    |
| CI                                        | testcontainers job on IRIS 2024.3, `latest-em`, `latest-preview`                                        | GitHub service containers: 2026.2 and 2026.3 on Python 3.10 to 3.12 by dbt-core 1.11 and 1.12, one 2026.1 job, Python models, and the example project              |                                                                                                                                                 |
| IRIS releases                             | 2024.3 and later in CI                                                                                  | 2026.1 and later                                                                                                                                                   | Only 2026.1 to 2026.3 were tested. Nothing known breaks on 2024.3 or 2025.x; they simply were not run                                           |

## New in 2.0.0, with no 1.9.x counterpart

- **What the server accepts, asked once.** The adapter probes for `MERGE` and `WITH RECURSIVE` on
  each server, with statements that change nothing, and caches the answer. A model with
  `WITH RECURSIVE` on a server without it fails before it runs, with a message naming the IRIS
  version.
- **Guardrails against silent wrong data.** IRIS accepts these and stores or returns wrong results
  with no error, so the adapter refuses them with a message naming the fix:
  - a `UNION` whose branches give one column a `DATE` or `TIME` and another type (a table built
    from it stores `'66154'` for 2022-02-14);
  - a `GROUP BY` with a column number (IRIS reads `GROUP BY 1` as the constant 1, as its SQL
    reference documents, so every row falls into one group).
- **Cached queries after a column change or a table swap.** On IRIS 2026.3, for a user with
  `%All`, a statement another connection prepared before an `ALTER TABLE ... ADD COLUMN`, or
  before dbt renamed a rebuilt table into place, fails afterwards with "Invalid number of
  parameters". After each such change the adapter runs `PURGE CACHED QUERIES BY TABLE` from a
  second connection (the purge has no effect from the connection that made the change). It skips
  this on releases before 2026.3, which do not have the defect.
- **Background tuning that holds a lock.** With IRIS's adaptive mode (the default), the first
  query of a table starts an automatic tune, and a background worker then regenerates the
  table's cached queries while holding their metadata lock, for up to about two minutes. A
  statement prepared in that window fails with SQLCODE -114. The statement never ran, so the
  adapter sends it again.
- **Users without `%Developer`.** IRIS refuses `CREATE FUNCTION` and `CREATE PROCEDURE` with code
  to a user with only SQL privileges. 1.9.x failed every run on a new schema for such a user,
  because it installs `HASH()` there; 2.0.0 warns and runs everything except snapshots and Python
  models.
- **Seed collation.** `iris_collation: exact` gives seed string columns `%EXACT` collation, so they
  keep their case in `GROUP BY` and compare case-sensitively, as on other warehouses.
- **Documentation** in `docs/` and an example project, `examples/jaffle_shop`, built in CI.

## How CTEs are handled now

The bundled driver rewrote CTEs on the client, so every shape it understood ran. The official
driver sends SQL as written, and IRIS accepts a leading `WITH`, chained CTEs and CTEs with a column
list, but refuses a `WITH` anywhere else. The adapter moves those CTEs:

| Shape                                                                            | IRIS as written   | 2.0.0                                                 |
| -------------------------------------------------------------------------------- | ----------------- | ----------------------------------------------------- |
| Leading `WITH`, chained CTEs, column list `x(a)`                                 | Accepted          | Sent as written                                       |
| A CTE nested in another CTE (an ephemeral model with its own CTEs)               | SQLCODE -400      | Inner CTEs moved before the CTE that uses them        |
| `WITH` inside a derived table, `IN (...)`, a `UNION` branch or a scalar subquery | SQLCODE -1 or -12 | Moved to the statement's top-level `WITH`             |
| dbt's own wrappers (`select ... from ( <model> )` for tests and column lookup)   | Refused           | The model's leading CTEs are placed above the wrapper |

If a moved CTE's name is already used at the top level, the statement is sent as written and
IRIS's error shows; renaming would mean rewriting references inside the model.

## What 2.0.0 gives up

- **Platforms.** The bundled driver was pure Python and installed anywhere. The official driver
  ships five wheels (Linux glibc x86-64 and aarch64, macOS, Windows 32- and 64-bit) and no source
  distribution, so 2.0.0 does not install on Alpine Linux (musl), and not on PyPy, ppc64le,
  s390x or 32-bit ARM. `pip install intersystems-irispython` on `python:3.12-alpine` fails with
  "No matching distribution found". A glibc image such as `python:3.12-slim` works.
- **Immunity from native crashes.** The official driver is a compiled extension, so a defect in it
  can end the dbt process instead of raising an exception. The next section lists the shapes that
  still do this.
- **Plain rows.** The official driver returns row objects that cannot be read once their cursor
  is closed. The adapter copies rows out before dbt reads them.

## Crashes still possible in the official driver

These shapes end the process, hang, or leave the connection unusable with
`intersystems-irispython` 5.4.1. All of them also reproduce on 5.4.0; 5.4.1 changed none of them.
None is on a path dbt-iris uses, which is why the suite has not crashed in any run. That is an
argument from the code paths and from the absence of crashes, not a proof.

| Shape                                                                                      | What happens                                                                                                  | Does dbt-iris do it                                                                                                        |
| ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| A statement sent a second time, on a new cursor, with the wrong number of parameter values | The process ends (19 of 20 runs)                                                                              | No. Seeds use `executemany` with a fixed column count, and other statements have no parameters                             |
| `cursor.scroll()` on a live result set                                                     | Memory grows without bound; past either end it returns a row from the other end, and `close()` then segfaults | No. dbt-iris never scrolls                                                                                                 |
| `callproc("Name")` after `callproc("? = Name()")` for the same routine                     | Segfault, macOS wheel only                                                                                    | No. dbt-iris never calls `callproc`                                                                                        |
| A cursor closed, or reused, while it still has rows to fetch                               | The connection fails afterwards with "Message out of order"                                                   | Not on any path we found: dbt-iris reads in full every result it fetches                                                   |
| Two cursors reading large results on one connection at once                                | Each reads the other's rows; `fetchmany` can then block for ever                                              | No. Each dbt thread has its own connection and reads one result at a time; the cached-query purge opens its own connection |
| One cursor used from several threads                                                       | Segfault in some runs                                                                                         | No                                                                                                                         |
| A connection used after `fork()`                                                           | Five different outcomes, including a hang                                                                     | No. dbt runs threads, not forked processes, after connecting                                                               |
| The Native API (not DB-API) shared across three or more threads                            | Calls never return                                                                                            | No. dbt-iris does not use the Native API                                                                                   |

If you have cases where the official driver crashed for you, they are exactly what we want to
test next, and we will take them to the driver team first.

## Silent wrong results in IRIS that the adapter cannot fix

- **`GROUP BY` with a column number** (refused, as above). A feature request for IRIS to accept
  column numbers, as it does in `ORDER BY`, is being filed.
- **A `UNION` of a `DATE` or `TIME` and another type** stored by `CREATE TABLE AS` or
  `INSERT ... SELECT` (refused where the adapter can see it). Reported to InterSystems as a defect.
- **Case-insensitive strings by default.** `'female' = 'Female'` is true and `GROUP BY` returns
  `'FEMALE'`. This is IRIS's documented default; `iris_collation: exact` covers seeds.

The user guide's [IRIS SQL page](https://github.com/isc-tdyar/dbt-iris/blob/pr/guide/docs/iris-sql.md)
lists every difference we measured, with what to write instead.

## Upgrading

The [README](https://github.com/isc-tdyar/dbt-iris/blob/pr/guide/README.md#upgrading-from-19x)
has the five steps. The one that surprises people: `pip install -U dbt-iris` from 1.9.x deletes
the official driver's `iris/__init__.py` (because the 1.9.x wheel owned that file), so the driver
has to be reinstalled once with `pip install --force-reinstall --no-deps intersystems-irispython`.
