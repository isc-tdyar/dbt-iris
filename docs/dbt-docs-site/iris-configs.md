---
title: "InterSystems IRIS configurations"
id: "iris-configs"
---

<!-- Draft for a pull request to dbt-labs/docs.getdbt.com at
     website/docs/reference/resource-configs/iris-configs.md -->

## Materializations

`table`, `view`, `incremental`, `ephemeral`, seeds, snapshots and tests are supported. A view
is a real SQL view. IRIS has no `ALTER VIEW ... RENAME`, so when dbt renames a view the adapter
recreates it from its stored definition.

Materialized views are not supported, because IRIS does not have them.

## Incremental strategies

| Strategy        | How it runs on IRIS                                                                                                 |
| --------------- | ------------------------------------------------------------------------------------------------------------------- |
| `append`        | `INSERT ... SELECT` of the new rows                                                                                  |
| `merge`         | `MERGE` when the server accepts it; otherwise an `UPDATE ... FROM` of matched rows and an `INSERT ... WHERE NOT EXISTS` of new ones, in one transaction. No index on `unique_key` is needed. Supports `merge_update_columns`, `merge_exclude_columns` and `incremental_predicates` |
| `delete+insert` | Deletes the target rows that match a source row on `unique_key`, then inserts. The default when `unique_key` is set |
| `microbatch`    | Deletes the target rows in the batch's `event_time` window, then inserts the batch                                    |

A single-column `unique_key` matches NULL to NULL, as dbt's default merge does. Composite keys
use plain equality.

## Capability checks

The adapter asks the server once per connection target whether it accepts `MERGE` and
`WITH RECURSIVE`, and caches the answer.

- A model whose SQL uses `WITH RECURSIVE` on a server that does not accept it fails before it
  runs, with a message saying so. Recursive CTEs need an IRIS build that supports them.
- `merge` uses `MERGE` as soon as the server accepts it, with the same results.

## Snapshots

Snapshots use a `HASH` SQL function written in ObjectScript, so they need no Embedded Python on
the server. It returns the same values as earlier dbt-iris releases, so existing snapshot history
stays valid.

## Python models

Python models run in IRIS's Embedded Python. The server needs Embedded Python configured and
`pandas`, `sqlalchemy` and `sqlalchemy-iris` installed in IRIS's Python, for example:

```shell
python3 -m venv /tmp/pipv
/tmp/pipv/bin/pip install --target /usr/irissys/mgr/python pandas sqlalchemy sqlalchemy-iris
```

## SQL that IRIS does not accept

The adapter rewrites these where dbt generates them:

- A `WITH` clause inside a derived table, and a `WITH` nested in another CTE (ephemeral models
  with their own CTEs).
- Multi-row `INSERT ... VALUES (...), (...)`. Seeds use `executemany`; in your own SQL write
  `INSERT ... SELECT ... UNION ALL`.

## Running dbt more than once at a time

Temporary, intermediate and backup tables carry the invocation id, so overlapping `dbt run`
processes do not collide on them, and DDL that meets another process's lock is retried. Two
runs that replace the same models at the same time can still block each other on IRIS class
locks, and on every IRIS build tried this has also left a view's class damaged or the server
refusing connections. dbt does not support overlapping runs of one project: do not start a
second `dbt run` on the same models while one is running.
