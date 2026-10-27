# Changelog

## 2.0.0 (unreleased)

dbt-iris 2.0.0 connects only through the InterSystems driver `intersystems-irispython`, fixes
two incremental strategies that added duplicate rows, and adds `microbatch`, current snapshot
features and checks for what the server supports. Upgrading from 1.9.x takes one extra `pip`
step and, for some incremental models, one full refresh: see
[Upgrading from 1.9.x](README.md#upgrading-from-19x).

### Breaking changes

- The bundled `intersystems_iris` 3.x driver is removed, and so is the `driver` choice. The
  adapter connects only through `intersystems-irispython` 5.4 or later (`iris.dbapi`). A profile
  or `DBT_IRIS_DRIVER` that names `vendored` or `sqlalchemy` fails with a message saying so;
  `driver: iris` is still accepted and does nothing.
- Requires dbt-core 1.10 or later (dbt-adapters 1.15.2 or later) and Python 3.10 or later.
- The `sqlalchemy` extra is removed. Python models still use `sqlalchemy-iris` inside the IRIS
  server's Python.
- `insert_overwrite` is removed. Its macro was an upsert, not an overwrite; use `merge`.
- The wheel ships only the `dbt` packages. 1.9.2 also carried `iris`, `intersystems_iris` and
  `irisnative`, copied in from the 3.x driver, so installing dbt-iris replaced
  `intersystems-irispython`'s `iris/__init__.py` and uninstalling it deleted that file. Upgrading
  from 1.9.x deletes it once more; reinstall `intersystems-irispython` afterwards.

### Fixes

- `delete+insert` matches rows with a null-safe `EXISTS`. 1.9.x matched with
  `IFNULL(key, '') IN (...)`, which deleted nothing for integer keys, so every run duplicated
  rows.
- `merge` runs as `UPDATE ... FROM` plus `INSERT ... WHERE NOT EXISTS` and needs no index on
  `unique_key`. 1.9.x used `INSERT OR UPDATE`, which duplicated rows on a target without a unique
  index, and tables dbt builds have none.
- Common table expressions with a column list work. The 3.x driver spoke an older xDBC protocol
  and rewrote most CTEs into subqueries on the client, and IRIS refused the ones it left, such as
  a CTE with a column list. The adapter now hoists leading CTEs above the `select ... from (...)`
  wrappers dbt uses for tests and column lookup, and flattens nested CTEs (ephemeral models with their own CTEs) and lifts a `WITH` out of a
  subquery (derived table, `IN`, `UNION` branch, scalar subquery) before `CREATE VIEW` and
  `CREATE TABLE AS`, because IRIS accepts none of these shapes.
- Python models run through `exec` of their base64-encoded code inside the IRIS stored procedure.
  IRIS re-indents every line of a `LANGUAGE PYTHON` body, which added tabs to the continuation
  lines of multi-line strings, and 1.9.x deleted every line starting with `#`, including lines
  inside strings.
- Python models check for `sqlalchemy_iris`, the package whose `iris+emb` dialect they use,
  instead of `intersystems_iris`. `dbt.ref()` inside a Python model finds quoted relations such as
  `"schema"."table"`.
- Snapshots read the snapshot time once per run, with microseconds. Two runs in the same second
  gave a changed row its predecessor's `dbt_scd_id`.
- `microbatch`'s event-time filters use IRIS timestamp literals. They compared a `TIMESTAMP`
  column with strings carrying a timezone offset, and matched no rows.
- `get_rows_different_sql` compares table contents. In 1.9.x it returned `SELECT 0,0`, so dbt's
  equality checks between relations could never fail.
- After the adapter adds or drops a table's columns, it purges the table's cached queries from a
  second connection. On IRIS 2026.3, for a user with `%All` such as `_SYSTEM`, a query another
  connection had run on the table otherwise failed with "Invalid number of parameters".
- `get_rows_different_sql` counts the rows on one side only with `UNION ALL` and `GROUP BY`. With
  `EXCEPT`, IRIS failed with SQLCODE -400 when one side was a view grouping by an `%EXACT` column.
- A user who may not create functions with ObjectScript code can run dbt. Installing `HASH`
  failed every run on a new schema; it is now a warning, and only snapshots need the
  `%Developer` role.
- The Dockerfile pins an image tag that exists (issue #7).

### New

- `microbatch` incremental strategy.
- A `table` or `incremental` model whose `UNION` gives a column a `DATE` or `TIME` in one branch
  and another type in another fails with a message naming the column. IRIS would store the
  values as internal numbers (`'66154'` for 2022-02-14) without an error.
- A statement with a column number in `GROUP BY` (`group by 1`) fails with a message. IRIS reads
  the number as a constant and would put every row into one group, without an error.
- `iris_collation: exact` for seeds: string columns keep their case in `GROUP BY` and compare
  case-sensitively, as on other warehouses. The default is unchanged.
- `merge` honours `merge_update_columns`, `merge_exclude_columns` and `incremental_predicates`,
  and uses `MERGE` when the server accepts it.
- Snapshots follow dbt 1.9's snapshot configuration: `snapshot_meta_column_names`,
  `dbt_valid_to_current`, a list `unique_key` and the three `hard_deletes` modes. `dbt_scd_id`
  hashing is unchanged.
- `materialized_view` models are built as tables, rebuilt on every run, so projects written for
  other warehouses run unchanged; IRIS has no materialized views. `iris_materialized_view_as: view`
  builds them as views instead, and `table` silences the warning that lists the models left on
  the default.
- The adapter checks once per server whether it accepts `MERGE` and `WITH RECURSIVE`. A model
  that uses `WITH RECURSIVE` on a server that does not accept it fails before it runs, with a
  message naming the IRIS version and pointing to a fixed-depth pattern that works on any IRIS.
  Only SQL errors answer the check; a dropped connection does not.
- `profile_template.yml` for `dbt init`.

### Changes

- A user guide in `docs/`: an overview of how the adapter works, a tutorial on the
  `examples/jaffle_shop` project (built in CI), a configuration reference, IRIS SQL differences,
  troubleshooting by error message, the dbt Fusion preview and a contributing guide.
- The `HASH` function used by snapshots is ObjectScript, so snapshots need no Embedded Python. It
  returns the same values as 1.9.x, including for the empty string, so existing snapshot history
  stays valid.
- Temporary, intermediate and backup tables carry the invocation id, so overlapping runs never
  share one, and none is left behind: an incremental run's temporary table and a snapshot's
  staging table are dropped when the model is done. DDL that meets another process's class lock
  is retried (issue #3).
- Statements without bindings are run as `cursor.execute(sql)`; the driver rejects an explicit
  `None`.
- Result rows are copied out of the cursor before dbt reads them. The driver's rows cannot be
  read once their cursor is closed, and dbt's test utilities read them after that.
- CI runs the dbt-tests-adapter suites against IRIS Community 2026.2 and 2026.3 (preview) on
  Python 3.10 to 3.12 with dbt-core 1.11 and 1.12, against 2026.1 on Python 3.12 with dbt-core
  1.12, and runs a Python models job.

### dbt Fusion (preview)

- Schema creation and lookup run as SQL macros, and seeds load as one ADBC bulk ingest when the
  engine is dbt Fusion. dbt-core keeps the Python methods and batched `INSERT`s. Using dbt Fusion
  with IRIS needs an IRIS ADBC driver and an IRIS adapter in dbt Fusion, neither published yet.
