# Configuration reference

Every setting dbt-iris reads, in one place: the profile that connects dbt to IRIS, then the model,
seed and snapshot configs, with what each one becomes in IRIS SQL. For how the pieces fit
together, see the [overview](overview.md); for walking through a first project, see the
[tutorial](tutorial.md).

## Profile

`~/.dbt/profiles.yml`, with `type: iris`:

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

| Setting            | Required | Aliases          | Default | Meaning                                                                                                 |
| ------------------ | -------- | ---------------- | ------- | ------------------------------------------------------------------------------------------------------- |
| `type`             | yes      |                  |         | Always `iris`                                                                                           |
| `hostname`         | yes      | `host`, `server` |         | Host name or address of the IRIS server                                                                 |
| `port`             | yes      |                  |         | The IRIS superserver port, usually 1972. `dbt init` offers 1972                                         |
| `database`         | yes      | `namespace`      |         | The IRIS namespace, such as `USER`. Not an IRIS database, which is the file a namespace's data lives in |
| `username`         | yes      | `user`           |         | IRIS user                                                                                               |
| `password`         | yes      | `pass`           |         | That user's password                                                                                    |
| `schema`           | yes      |                  |         | The SQL schema models are built in, the name before the dot in `schema.table`                           |
| `threads`          | no       |                  | 1       | How many models dbt builds at once. Each thread holds one IRIS connection, which uses a licence unit    |
| `application_name` | no       |                  | `dbt`   | Shown in `dbt debug`; not sent to IRIS                                                                  |
| `driver`           | no       |                  |         | Removed in 2.0.0. Only `iris` is accepted, and it does nothing; any other value fails the connection    |

`dbt init` asks for the same settings, and `dbt debug` checks the connection.

### Privileges

The IRIS user needs the SQL privileges to create, alter and drop tables and views in `schema`,
and to read the sources the models select from. Two features also need the `%Developer` role, or
another role that allows `CREATE FUNCTION` and `CREATE PROCEDURE` with code:

- **Snapshots** use a `HASH()` SQL function written in ObjectScript, which the adapter installs
  when it creates a schema.
- **Python models** run as a stored procedure written in Python.

Without that role, dbt warns once and runs everything else; see
[troubleshooting](troubleshooting.md#could-not-install-the-hash-sql-function).

### Environment variables

| Variable          | Meaning                                                                                     |
| ----------------- | ------------------------------------------------------------------------------------------- |
| `DBT_IRIS_DRIVER` | Removed in 2.0.0. `iris` is accepted and does nothing; any other value fails the connection |

Use dbt's own `env_var()` in `profiles.yml` to keep the password out of the file:
`password: "{{ env_var('IRIS_PASSWORD') }}"`.

## Materializations

Set with `materialized` in a model's `config()` or in `dbt_project.yml`.

| `materialized`      | What IRIS gets                                                                                                                                             |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `view` (default)    | `CREATE VIEW`. IRIS has no `ALTER VIEW ... RENAME`, so when dbt swaps a view in, the adapter recreates it from its definition                              |
| `table`             | `CREATE TABLE ... AS SELECT` into a new name, then renames swap it in place of the old table                                                               |
| `incremental`       | The first run, and `--full-refresh`, build a table as above. Later runs build the new rows in a temporary table and apply them with `incremental_strategy` |
| `ephemeral`         | No object. The model's SQL becomes a CTE in the models that use it; the adapter flattens nested CTEs, which IRIS does not accept                           |
| `materialized_view` | IRIS has no materialized views. Built as a table rebuilt on every run, or as a view, as `iris_materialized_view_as` says                                   |

Before it builds a `table` or `incremental` model whose SQL contains a `UNION`, the adapter
checks the column types of each branch, and fails the model if one column is `DATE` or `TIME` in
one branch and another type in another. See [IRIS SQL differences](iris-sql.md).

### `iris_materialized_view_as`

| Value   | Built as                                                                                        |
| ------- | ----------------------------------------------------------------------------------------------- |
| not set | A table, with one warning per run that lists the `materialized_view` models left on the default |
| `table` | A table, without the warning                                                                    |
| `view`  | A view, which always shows the current source rows and stores nothing                           |

Any other value fails the model before it runs. `on_configuration_change` is accepted and ignored.

```yaml
models:
  my_project:
    marts:
      +iris_materialized_view_as: view
```

## Incremental models

| Config                   | Values                                                     | Default   | Meaning on IRIS                                                                                                                                       |
| ------------------------ | ---------------------------------------------------------- | --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `incremental_strategy`   | `append`, `merge`, `delete+insert`, `microbatch`           | see below | How new rows reach the table. `insert_overwrite` is not offered                                                                                       |
| `unique_key`             | a column name, or a list of names                          | none      | The key `merge` and `delete+insert` match on. A single column matches NULL to NULL; a list uses plain equality on each column                         |
| `merge_update_columns`   | list of column names                                       | all       | `merge` only: the columns an update changes                                                                                                           |
| `merge_exclude_columns`  | list of column names                                       | none      | `merge` only: columns an update leaves alone                                                                                                          |
| `incremental_predicates` | list of SQL conditions                                     | none      | Extra conditions on the match (`merge`), the delete (`delete+insert`) or the window delete (`microbatch`), to limit how much of the target is scanned |
| `on_schema_change`       | `ignore`, `fail`, `append_new_columns`, `sync_all_columns` | `ignore`  | What happens when the model's columns change. Adding or dropping columns runs `ALTER TABLE`; the adapter then clears the table's cached queries       |

The default strategy is `delete+insert` when `unique_key` is set, and `append` when it is not.

| `incremental_strategy` | SQL on IRIS                                                                                                                                                                                   |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `append`               | `INSERT INTO target SELECT ... FROM` the temporary table                                                                                                                                      |
| `merge`                | `MERGE` when the server accepts it. Otherwise an `UPDATE target ... FROM` of the rows that match, then an `INSERT ... WHERE NOT EXISTS` of the rest. No primary key or unique index is needed |
| `delete+insert`        | `DELETE FROM target WHERE EXISTS (matching row in the temporary table)`, then `INSERT`                                                                                                        |
| `microbatch`           | `DELETE` of the target rows in the batch's `event_time` window, then `INSERT` of the batch                                                                                                    |

`microbatch` uses dbt's own configs: `event_time` (the column, on the model and on its inputs),
`batch_size` (`hour`, `day`, `month` or `year`), `begin`, and `lookback`. The window is compared
as IRIS timestamps.

## Snapshots

dbt-iris follows dbt's snapshot configuration from dbt-core 1.9.

| Config                       | Values                                         | Meaning                                                                     |
| ---------------------------- | ---------------------------------------------- | --------------------------------------------------------------------------- |
| `strategy`                   | `timestamp`, `check`                           | How a changed row is found                                                  |
| `unique_key`                 | a column name, or a list of names              | The row's identity                                                          |
| `updated_at`                 | a column                                       | `timestamp` strategy: the column that says when a row changed               |
| `check_cols`                 | `all`, or a list of columns                    | `check` strategy: the columns compared                                      |
| `hard_deletes`               | `ignore` (default), `invalidate`, `new_record` | What happens to a row that disappears from the source                       |
| `snapshot_meta_column_names` | mapping                                        | Other names for `dbt_valid_from`, `dbt_valid_to`, `dbt_scd_id` and the rest |
| `dbt_valid_to_current`       | a SQL expression                               | The `dbt_valid_to` of current rows, instead of NULL                         |

The snapshot time is read once per run, with microseconds. `dbt_scd_id` is computed with the
adapter's `HASH()` function, which gives the same values as dbt-iris 1.9.x, so existing snapshot
history stays valid. Snapshots need the privilege described under [Privileges](#privileges).

## Seeds

| Config           | Values                                  | Default   | Meaning                                                                                                                                                                                |
| ---------------- | --------------------------------------- | --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `column_types`   | mapping of column name to IRIS SQL type | inferred  | Overrides the type the adapter picks. Text columns default to `VARCHAR(65535)`, or longer when a value is longer                                                                       |
| `quote_columns`  | `true`, `false`                         | `true`    | Whether column names are quoted in the `CREATE TABLE`. Quoted names keep their case; set `false` for plain IRIS names                                                                  |
| `iris_collation` | `default`, `exact`                      | `default` | `default` keeps IRIS's case-insensitive string comparison. `exact` gives the seed's string columns `%EXACT` collation: they keep their case in `GROUP BY` and compare case-sensitively |

Tables and views built from a seed inherit its collation. Any other `iris_collation` value fails
the seed before it is created. `iris_collation` does not change `TEXT` columns, which IRIS stores
as streams.

```yaml
seeds:
  my_project:
    +iris_collation: exact
```

With `exact`, one IRIS issue applies: a view that groups by an `exact` column fails with SQLCODE
-400 when used in `EXCEPT` or in a correlated `NOT EXISTS`. dbt's own data tests use neither.

## Python models

Python models run inside IRIS, in its Embedded Python, as a stored procedure the adapter creates
for the run and drops afterwards. They are built as tables. The server needs:

- Embedded Python configured.
- `pandas`, `sqlalchemy` and `sqlalchemy-iris` installed into IRIS's Python, for example:

  ```shell
  python3 -m venv /tmp/pipv
  /tmp/pipv/bin/pip install --target /usr/irissys/mgr/python pandas sqlalchemy sqlalchemy-iris
  ```

- The privilege described under [Privileges](#privileges).

`dbt.ref()` and `dbt.source()` return pandas DataFrames read through `sqlalchemy-iris`, and the
model's returned DataFrame replaces the target table.
