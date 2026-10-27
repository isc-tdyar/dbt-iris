# dbt-iris

`dbt-iris` is the [dbt](https://www.getdbt.com/) adapter for
[InterSystems IRIS](https://www.intersystems.com/data-platform/). With it, dbt builds tables,
views, incremental models, snapshots, seeds and Python models in IRIS, and runs your tests there.
This README covers dbt-iris 2.0.0, maintained by CaretDev (Dmitry Maslennikov) and contributors.

The [documentation](docs/README.md) has the full guide. Upgrading from 1.9.x? Read
[Upgrading from 1.9.x](#upgrading-from-19x) before you run `pip`.

## Five-minute start

Install dbt and the adapter. `pip` also installs `intersystems-irispython`, the InterSystems
driver the adapter connects through:

```shell
python -m pip install dbt-core dbt-iris
```

Start IRIS Community with this repository's `docker-compose.yml` (its Dockerfile adds what Python
models need inside IRIS):

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

Add a profile to `~/.dbt/profiles.yml`. In dbt-iris, `database` is the IRIS namespace and `schema`
is the SQL schema the models are built in:

```yaml
my_project:
  target: dev
  outputs:
    dev:
      type: iris
      hostname: localhost
      port: 1972
      database: USER
      username: _SYSTEM
      password: SYS
      schema: dbt
      threads: 4
```

Check it with `dbt debug`, then `dbt build`. The [tutorial](docs/tutorial.md) walks through a
whole project, [`examples/jaffle_shop`](examples/jaffle_shop), step by step.

## Supported versions

| Component                 | Supported       | Tested                              |
| ------------------------- | --------------- | ----------------------------------- |
| dbt-core                  | 1.10 or later   | 1.11 and 1.12                       |
| Python                    | 3.10 or later   | 3.10, 3.11 and 3.12                 |
| `intersystems-irispython` | 5.4 or later    | 5.4.1                               |
| InterSystems IRIS         | 2026.1 or later | 2026.1, 2026.2 and 2026.3 (preview) |

dbt's adapter test suites pass in full on IRIS 2026.1.0.234, 2026.2.0.221 and 2026.3.0L.196.
dbt-core 1.10 and Python 3.10 are the minimums; dbt Fusion is [in preview](docs/fusion.md).

## What works

- **Materializations:** `table`, `view`, `incremental`, `ephemeral` and `materialized_view` (built
  as a table or a view; IRIS has no materialized views), plus seeds, snapshots and tests.
- **Incremental strategies:** `append`, `merge`, `delete+insert` (the default with a
  `unique_key`) and `microbatch`. `merge` needs no index on `unique_key`.
- **Snapshots:** `check` and `timestamp`, multi-column keys and all three `hard_deletes` modes.
- **Python models:** run inside IRIS, in Embedded Python.

## Before you write models

IRIS SQL differs from other warehouses in a few places. These are the ones that matter most; the
[IRIS SQL page](docs/iris-sql.md) has the full list with what to write instead.

- **`GROUP BY 1` groups by the number 1.** Name the columns. `ORDER BY 1` works.
- **Strings compare without regard to case** by default, and `GROUP BY` returns the upper-case
  form. Use `%EXACT(col)`, or `iris_collation: exact` on seeds.
- **A `UNION` that mixes `DATE` or `TIME` with another type** would be stored wrongly, so the
  adapter refuses to build a table from it and names the column. Cast every branch to one type.
- **No `WITH RECURSIVE` or `MERGE`** on any release yet. The `merge` strategy works without
  `MERGE`; a recursive model fails with a message naming the IRIS version.
- **Snapshots and Python models need the `%Developer` role** (or equivalent) on top of SQL
  privileges. Without it, dbt warns and runs the rest.
- **Do not start overlapping runs of one project.** Two `dbt run` processes replacing the same
  models at once can block each other on IRIS class locks and can damage the IRIS catalog.

When something fails, the [troubleshooting page](docs/troubleshooting.md) lists the messages and
their fixes.

## Documentation

- [Overview](docs/overview.md): how dbt-iris works and what each materialization does in IRIS.
- [Tutorial](docs/tutorial.md): from nothing to `dbt build` on the example project.
- [Configuration](docs/configuration.md): every profile setting and model, seed and snapshot
  config.
- [IRIS SQL differences](docs/iris-sql.md): what to write differently for IRIS.
- [Troubleshooting](docs/troubleshooting.md): error messages, causes and fixes.
- [dbt Fusion (preview)](docs/fusion.md): what works today and what is missing.
- [Contributing](docs/contributing.md): running the tests against IRIS in Docker.

The pages for docs.getdbt.com are drafted in [iris-setup](docs/dbt-docs-site/iris-setup.md) and
[iris-configs](docs/dbt-docs-site/iris-configs.md).

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

## Links

- [CHANGELOG.md](CHANGELOG.md)
- [InterSystems Documentation](https://docs.intersystems.com/)
- [InterSystems Developer Community](https://community.intersystems.com/)
