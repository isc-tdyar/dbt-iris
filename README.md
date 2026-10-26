# dbt-iris

`dbt-iris` is the [dbt](https://www.getdbt.com/) adapter for
[InterSystems IRIS](https://www.intersystems.com/data-platform/). It lets you build tables, views,
incremental models, snapshots and Python models in IRIS with dbt, the same way you would on any
other warehouse. This README covers dbt-iris 2.0.0. It is maintained by CaretDev (Dmitry
Maslennikov) and contributors.

If you know dbt but not IRIS, read [How dbt names map to IRIS](#how-dbt-names-map-to-iris) and
[IRIS SQL notes](#iris-sql-notes) first: they are where IRIS differs from the warehouses you know.
Upgrading from 1.9.x? Read [Upgrading from 1.9.x](#upgrading-from-19x) before you run `pip`.

## Install

```shell
python -m pip install dbt-core dbt-iris
```

`pip` also installs `intersystems-irispython`, the InterSystems DB-API driver the adapter
connects through.

## Supported versions

| Component                 | Supported       | Tested                                         |
| ------------------------- | --------------- | ---------------------------------------------- |
| dbt-core                  | 1.10 or later   | 1.11 and 1.12                                  |
| Python                    | 3.10 or later   | 3.10, 3.11 and 3.12                            |
| `intersystems-irispython` | 5.4 or later    | 5.4.1                                          |
| InterSystems IRIS         | 2026.1 or later | 2026.1, 2026.2 and 2026.3 (preview), see below |

dbt's adapter test suites pass on each of these IRIS builds. The tests that fail because of an
IRIS issue are marked as expected failures, and the issues are:

| IRIS             | Build tested  | Known IRIS issues                                                                                                                                                                                      |
| ---------------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 2026.1           | 2026.1.0.234  | [`UNION` of a `DATE` and text](#iris-sql-notes); [`GROUP BY` case](#iris-sql-notes)                                                                                                                    |
| 2026.2           | 2026.2.0.221  | The same two                                                                                                                                                                                           |
| 2026.3 (preview) | 2026.3.0L.196 | The same two, and a query on a table another connection has just altered with `ADD COLUMN` can fail with "Invalid number of parameters"; in dbt this shows up in snapshots whose source gains a column |

None of these releases accepts recursive CTEs; see [Recursive CTEs](#recursive-ctes).

## Start InterSystems IRIS locally

This repository's `docker-compose.yml` starts IRIS Community. Its Dockerfile adds the packages
Python models need inside IRIS:

```yml
services:
  iris:
    build: .
    command:
      - -a
      # by default it starts with a requirement to change passwords for system users
      - iris session iris -U %SYS '##class(Security.Users).UnExpireUserPasswords("*")'
    ports:
      - 1972:1972
      - 52773:52773
```

```shell
docker compose up -d
```

dbt connects on port 1972, the IRIS superserver. The Management Portal is at
[http://localhost:52773/csp/sys/UtilHome.csp](http://localhost:52773/csp/sys/UtilHome.csp). The
login is `_SYSTEM` / `SYS`.

## Configure dbt

`~/.dbt/profiles.yml`:

```yaml
my_project:
  target: dev
  outputs:
    dev:
      type: iris
      hostname: localhost
      port: 1972
      database: USER # the IRIS namespace; `namespace` also works
      username: _SYSTEM
      password: SYS
      schema: dbt
      threads: 4
```

`dbt init` asks for the same settings, and `dbt debug` checks the connection. Every setting and
its aliases are listed on the [setup page](docs/dbt-docs-site/iris-setup.md).

The user needs the SQL privileges to create tables and views in `schema`, and to create the
`HASH` SQL function the adapter installs for snapshots.

### How dbt names map to IRIS

| dbt                       | IRIS                                                                              |
| ------------------------- | --------------------------------------------------------------------------------- |
| `database`                | Namespace, such as `USER`. Not an IRIS database, which is a namespace's data file |
| `schema`                  | SQL schema, the name before the dot in `schema.table`                             |
| `materialized_view` model | A table rebuilt on every run, or a view; IRIS has no materialized views           |

## Incremental strategies

- `append`: inserts the new rows.
- `merge`: `MERGE` when the server accepts it, otherwise an `UPDATE` of matched rows and an
  `INSERT` of new ones. No index on `unique_key` is needed. `merge_update_columns`,
  `merge_exclude_columns` and `incremental_predicates` are honoured.
- `delete+insert`: the default when `unique_key` is set.
- `microbatch`: replaces each batch's `event_time` window.

`insert_overwrite` is not offered. The [configs page](docs/dbt-docs-site/iris-configs.md) says
how each strategy runs on IRIS.

## Snapshots

Snapshots support `check` and `timestamp` strategies, multi-column `unique_key`,
`snapshot_meta_column_names`, `dbt_valid_to_current` and all three `hard_deletes` modes. They
need no Embedded Python on the server: the adapter's `HASH` function is ObjectScript, and returns
the same values as earlier releases, so existing snapshot history stays valid.

## Python models

Python models run in IRIS's Embedded Python. Install `pandas`, `sqlalchemy` and `sqlalchemy-iris`
into IRIS's Python on the server, as this repository's Dockerfile does.

## Recursive CTEs

dbt never generates recursive SQL, so this only matters for models you write with
`WITH RECURSIVE` yourself. Those need an IRIS release that supports recursive CTEs. On a server
that does not, the model fails before it runs, with a message naming the IRIS version. The
[configs page](docs/dbt-docs-site/iris-configs.md#recursive-ctes) shows a fixed-depth pattern
that works on any IRIS.

## IRIS SQL notes

- **CTEs in subqueries.** IRIS does not accept a `WITH` clause inside a derived table, or a
  `WITH` nested inside another CTE's body. The adapter rewrites both shapes, so ephemeral models
  and models with their own CTEs work as tests, views and tables.
- **Multi-row `VALUES`.** `INSERT ... VALUES (...), (...)` is not IRIS SQL. Seeds are loaded
  with `executemany`; write your own inserts as `INSERT ... SELECT ... UNION ALL`.
- **`UNION` of a `DATE` and text.** Give every branch of a `UNION` the same type. When one branch
  is a `DATE` and another is text, a plain query returns the right values, but a table built from
  it (every `table` and `incremental` model) stores the date's internal day number, for example
  `'66154'`.
- **`GROUP BY` case.** `GROUP BY` on a string column returns the value in upper case (`'FEMALE'`
  for `'Female'`), the IRIS default. Group by `%EXACT(col)` to keep the original case.
- **Renaming views.** IRIS has no `ALTER VIEW ... RENAME`; the adapter recreates the view from its
  definition instead.
- **Materialized views.** IRIS has none. A `materialized_view` model is built as a table, rebuilt
  on every `dbt run`. Set `iris_materialized_view_as: view` to build it as a view, or `table` to
  keep the table without the warning that lists the models left on the default. For a large model
  that is rebuilt often, `incremental` is cheaper.

## Running dbt more than once at a time

Temporary, intermediate and backup tables carry the dbt invocation id, so overlapping `dbt run`
processes do not collide on them, and DDL that meets another process's lock is retried. Two runs
replacing the same models at the same time can still block each other on IRIS class locks, and
can damage the IRIS catalog. dbt does not support overlapping runs of one project: do not start a
second `dbt run` on the same models while one is running.

## dbt Fusion (preview)

dbt-iris 2.0.0 carries the macros dbt Fusion, the new dbt engine, needs for IRIS: schema creation and lookup run as SQL macros, and seeds load as one bulk ingest instead of
batched `INSERT`s. dbt-core runs exactly as before. Using it needs an IRIS ADBC driver and an IRIS
adapter in dbt Fusion, and **neither is published yet**. Until they are, dbt-iris works with
dbt-core only.

## Upgrading from 1.9.x

1. **Reinstall the driver after upgrading.** dbt-iris 1.9.x shipped its own copy of the `iris`
   package. When `pip install -U dbt-iris` removes 1.9.x, it deletes `iris/__init__.py` from
   `intersystems-irispython` too, and dbt then fails with
   `AttributeError: module 'iris' has no attribute 'irissdk'`. Upgrade, then reinstall the driver:

   ```shell
   python -m pip install -U dbt-iris
   python -m pip install --force-reinstall --no-deps intersystems-irispython
   ```

2. **Remove the `driver` setting.** There is no driver choice any more. `driver: iris` is accepted
   and does nothing; `vendored` or `sqlalchemy`, in the profile or in `DBT_IRIS_DRIVER`, fails
   with a message.
3. **Check dbt-core and Python.** dbt-iris 2.0.0 needs dbt-core 1.10 or later and Python 3.10 or
   later.
4. **Rebuild incremental models that 1.9.x duplicated.** 1.9.x added duplicate rows on every run
   in two cases: `delete+insert` models with an integer `unique_key`, and `merge` models whose
   target had no unique index (any table dbt built). 2.0.0 adds no new duplicates but leaves the
   old ones in place. Rebuild those models once:

   ```shell
   dbt run --full-refresh --select my_incremental_model
   ```

5. **Replace `insert_overwrite` with `merge`.** `insert_overwrite` is removed. Its 1.9.x macro
   updated matching rows and inserted new ones rather than overwriting, which is what `merge`
   does.

Everything else in [CHANGELOG.md](CHANGELOG.md) works without changes to your project.

## Useful links

- [CHANGELOG.md](CHANGELOG.md)
- [InterSystems Documentation](https://docs.intersystems.com/)
- [InterSystems Developer Community](https://community.intersystems.com/)
