<p align="center">
  <img src="https://raw.githubusercontent.com/dbt-labs/dbt/ec7dee39f793aa4f7dd3dae37282cc87664813e4/etc/dbt-logo-full.svg" alt="dbt logo" width="500"/>
</p>

**[dbt](https://www.getdbt.com/)** enables data analysts and engineers to transform their data using the same practices that software engineers use to build applications.

dbt is the T in ELT. Organize, cleanse, denormalize, filter, rename, and pre-aggregate the raw data in your warehouse so that it's ready for analysis.

## InterSystems IRIS

[InterSystems IRIS](https://www.intersystems.com/data-platform/) is a data platform with a
high-performance multi-model database. `dbt-iris` is its dbt adapter.

### Install

```shell
python -m pip install dbt-core dbt-iris
```

dbt-iris 2.0.0 needs dbt-core 1.10 or later and Python 3.10 or later. It connects through
`iris.dbapi` from `intersystems-irispython`, which `pip` installs with it. It is tested against
IRIS Community 2026.2 and 2026.3.

Connection settings: [docs/dbt-docs-site/iris-setup.md](docs/dbt-docs-site/iris-setup.md).
Configuration, strategies and limits: [docs/dbt-docs-site/iris-configs.md](docs/dbt-docs-site/iris-configs.md).

### Start InterSystems IRIS locally with Docker Compose

docker-compose.yml (in this repository; the Dockerfile adds the packages Python models need):

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

Port 1972 is the superserver; the Management Portal is on
[http://localhost:52773/csp/sys/UtilHome.csp](http://localhost:52773/csp/sys/UtilHome.csp).
The default login is `_SYSTEM` / `SYS`.

### Configure dbt

`~/.dbt/profiles.yml`:

```yaml
my_project:
  target: dev
  outputs:
    dev:
      type: iris
      hostname: localhost
      port: 1972
      database: USER      # the IRIS namespace; `namespace` also works
      username: _SYSTEM
      password: SYS
      schema: dbt
      threads: 4
```

`dbt init` prompts for the same settings. Since 2.0.0 there is no driver choice: the old
`driver` setting accepts only `iris`, and `vendored` or `sqlalchemy` (in the profile or in
`DBT_IRIS_DRIVER`) fails with a message.

### Incremental strategies

- `append`: insert the new rows.
- `merge`: `MERGE` when the server accepts it, otherwise an `UPDATE` of matched rows and an
  `INSERT` of new ones. No index on `unique_key` is needed. `merge_update_columns`,
  `merge_exclude_columns` and `incremental_predicates` are honoured.
- `delete+insert`: the default when `unique_key` is set.
- `microbatch`: replaces each batch's `event_time` window.

`insert_overwrite` is not offered.

### Snapshots

Snapshots need no Embedded Python on the server: the adapter's `HASH` function is ObjectScript,
and returns the same values as earlier releases.

### Python models

Python models run in IRIS's Embedded Python. Install `pandas`, `sqlalchemy` and
`sqlalchemy-iris` into IRIS's Python on the server, as the Dockerfile does.

### Recursive CTEs

Models that use `WITH RECURSIVE` need an IRIS build that supports recursive CTEs. On a server
that does not, such a model fails before it runs, with a message saying so.

### IRIS SQL notes

- A `WITH` clause may not appear inside a derived table, and a `WITH` nested inside another
  CTE's body fails to compile on the server. The adapter rewrites both shapes, so ephemeral
  models and models with their own CTEs work as tests, views and tables.
- Multi-row `INSERT ... VALUES (...), (...)` is not IRIS SQL. Seeds are loaded with
  `executemany`; write your own inserts as `INSERT ... SELECT ... UNION ALL`.
- IRIS has no `ALTER VIEW ... RENAME`; the adapter recreates a view from its definition instead.
  Materialized views are not supported.

### Running dbt more than once at a time

Temporary, intermediate and backup tables carry the invocation id, so overlapping `dbt run`
processes do not collide on them, and DDL that meets another process's lock is retried. Two
runs replacing the same models at the same time can still block each other on IRIS class
locks or catalog errors: dbt does not support overlapping runs of one project, and the losing
run fails with an IRIS lock or catalog error.

## What changed in 2.0.0

See [CHANGELOG.md](CHANGELOG.md). In short: the bundled 3.x driver is gone, dbt-core 1.10 and
Python 3.10 are required, `merge` and `delete+insert` are fixed for targets without a unique
index and for integer keys, `microbatch` is new, and snapshots no longer need Embedded Python.

## Useful Links

- [InterSystems Documentation](https://docs.intersystems.com/)
- [InterSystems Developer Community](https://community.intersystems.com/)
