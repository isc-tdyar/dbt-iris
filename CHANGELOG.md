# Changelog

## 2.0.0

### Breaking changes

- The bundled `intersystems_iris` 3.x driver is removed, and so is the `driver`
  choice. The adapter connects only through `intersystems-irispython` 5.4 or
  later (`iris.dbapi`). A profile or `DBT_IRIS_DRIVER` that names `vendored` or
  `sqlalchemy` now fails with a message saying so; `driver: iris` is still
  accepted and does nothing.
- Requires dbt-core 1.10 or later (dbt-adapters 1.15.2 or later) and Python 3.10
  or later.
- The `sqlalchemy` extra is removed. Python models still use `sqlalchemy-iris`
  inside the IRIS server's Python.

### Changes

- `merge` runs as `UPDATE ... FROM` plus `INSERT ... WHERE NOT EXISTS` and needs no index on
  `unique_key`; it honours `merge_update_columns`, `merge_exclude_columns` and
  `incremental_predicates`, and switches to `MERGE` when the server accepts it. 1.9.x used
  `INSERT OR UPDATE`, which duplicated rows on a target without a unique index.
- `delete+insert` matches rows with a null-safe `EXISTS`. 1.9.x matched with
  `IFNULL(key, '') IN (...)`, which deleted nothing for integer keys, so every run duplicated
  rows.
- New `microbatch` strategy. Event-time filters use IRIS timestamp literals.
- `insert_overwrite` is removed; its macro was an upsert, not an overwrite.
- The `HASH` function used by snapshots is ObjectScript, so snapshots need no Embedded Python.
  It returns the same values as 1.9.x, including for the empty string.
- Connect-time checks for `MERGE` and `WITH RECURSIVE`. A model that uses `WITH RECURSIVE` on a
  server that does not accept it fails with a plain message. CTE flattening keeps
  `WITH RECURSIVE` when it hoists a recursive ephemeral model.
- Backup tables carry the invocation id like temporary tables, and DDL that meets another
  process's class lock is retried (issue #3).
- `materialized_view` models are built as tables, rebuilt on every run, with a warning; IRIS has
  no materialized views. Projects written for other warehouses run unchanged.
- Python models run through `exec` of their base64-encoded code inside the IRIS stored
  procedure. IRIS re-indents every line of a `LANGUAGE PYTHON` body, which added tabs to the
  continuation lines of multi-line strings, and 1.9.x deleted every line starting with `#`,
  including lines inside strings, to work around comment trouble.
- `profile_template.yml` for `dbt init`. CI runs the dbt-tests-adapter suites against IRIS
  Community 2026.2 and 2026.3 on Python 3.10 to 3.12 and dbt-core 1.11 and 1.12, plus a Python
  models job. The Dockerfile pins an image tag that exists (issue #7).

- Connect through `intersystems-irispython` (`iris.dbapi`). The
  `intersystems_iris` 3.x driver previously downloaded by `requirements-iris.txt`
  and bundled into the wheel is no longer required; its download URL no longer
  resolves. The 3.x driver speaks xDBC protocol 65 and rewrites most CTEs into
  subqueries on the client; IRIS refuses the CTEs it does not rewrite (SQLCODE
  -385 for a CTE with a column list, protocol 65 where 69 is required; SQLCODE
  -400 for `WITH RECURSIVE`). The 5.x driver speaks protocol 69.
- Statements without bindings are executed as `cursor.execute(sql)`; the
  `intersystems-irispython` driver rejects an explicit `None`.
- Result rows are copied out of the cursor before dbt reads them. The compiled
  driver returns `DataRow` proxies that become inaccessible once the cursor is
  closed; dbt's test utilities read results after that point.
- IRIS SQL cannot place a `WITH` clause inside a derived table, and its SQL
  server fails to compile a `WITH` nested inside another CTE's body (SQLCODE
  -400, `<UNDEFINED> %qinfo("type")`). The adapter now hoists leading CTEs
  above the `select ... from (...)` wrappers used for tests and column
  introspection, and flattens nested CTEs (ephemeral models that have their own
  CTEs) before `CREATE VIEW` and `CREATE TABLE AS`. The old bundled driver did
  equivalent rewriting client-side.
- Test fixtures that used multi-row `INSERT ... VALUES (...), (...)`, which
  IRIS does not accept, now use `INSERT ... SELECT ... UNION ALL`.
- Unit tests for the driver, row detachment, CTE hoisting and flattening.
- The wheel ships only the `dbt` packages. 1.9.2 also carried `iris`,
  `intersystems_iris` and `irisnative`, copied in at build time from the 3.x
  driver, so installing dbt-iris replaced `intersystems-irispython`'s
  `iris/__init__.py` and uninstalling it deleted that file. `requirements-iris.txt`
  and the copy step in `scripts/build-dist.sh` are removed.
- Python models check for `sqlalchemy_iris`, the package whose `iris+emb`
  dialect they use, instead of `intersystems_iris`. `dbt.ref()` inside a Python
  model now finds quoted relations such as `"schema"."table"`.
- `TestPythonModelIRIS` runs when `DBT_IRIS_PYTHON_MODELS=1`; it needs pandas
  and sqlalchemy-iris installed in the IRIS server's Python.
