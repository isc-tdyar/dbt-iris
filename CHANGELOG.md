# Changelog

## Unreleased

- Connect through `intersystems-irispython` (`iris.dbapi`) by default. The
  `intersystems_iris` 3.x driver previously downloaded by `requirements-iris.txt`
  and bundled into the wheel is no longer required; its download URL no longer
  resolves. Models using a `WITH` clause now run: IRIS refuses CTE statements
  from that driver's xDBC protocol version (SQLCODE -385, protocol 65 where 69
  is required), which the 5.x driver satisfies.
- New profile field `driver` (or `DBT_IRIS_DRIVER` env var): `iris`,
  `sqlalchemy`, or `vendored`. `sqlalchemy` is an optional extra.
- Statements without bindings are executed as `cursor.execute(sql)`; the
  `intersystems-irispython` driver rejects an explicit `None`.
- `SQLType` is resolved from whichever driver is installed.
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
- Unit tests for driver selection, row detachment, CTE hoisting and flattening.
- The wheel ships only the `dbt` packages. 1.9.2 also carried `iris`,
  `intersystems_iris` and `irisnative`, copied in at build time from the 3.x
  driver, so installing dbt-iris replaced `intersystems-irispython`'s
  `iris/__init__.py` and uninstalling it deleted that file. `requirements-iris.txt`
  and the copy step in `scripts/build-dist.sh` are removed.
