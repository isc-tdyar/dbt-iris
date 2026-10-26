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

IRIS has no materialized views. A `materialized_view` model is built as a table by default,
rebuilt on every `dbt run` and not refreshed in between, so projects written for other
warehouses run unchanged. `on_configuration_change` is accepted and ignored.

| `iris_materialized_view_as` | Built as                                                                            |
| --------------------------- | ----------------------------------------------------------------------------------- |
| not set                     | A table, with one warning per run listing the `materialized_view` models left unset |
| `table`                     | A table, without the warning                                                        |
| `view`                      | A view, which always shows the current source rows and stores nothing               |

Any other value fails the model before it runs. Set it per model or for a folder:

```yaml
models:
  my_project:
    marts:
      +iris_materialized_view_as: view
```

Rebuilding the table costs about as much as running the query and writing every row again on
each run. For a large model, `incremental` avoids the full rebuild.

## Incremental strategies

| Strategy        | How it runs on IRIS                                                                                                                                                                                                                                                                |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `append`        | `INSERT ... SELECT` of the new rows                                                                                                                                                                                                                                                |
| `merge`         | `MERGE` when the server accepts it; otherwise an `UPDATE ... FROM` of matched rows and an `INSERT ... WHERE NOT EXISTS` of new ones, in one transaction. No index on `unique_key` is needed. Supports `merge_update_columns`, `merge_exclude_columns` and `incremental_predicates` |
| `delete+insert` | Deletes the target rows that match a source row on `unique_key`, then inserts. The default when `unique_key` is set                                                                                                                                                                |
| `microbatch`    | Deletes the target rows in the batch's `event_time` window, then inserts the batch                                                                                                                                                                                                 |

A single-column `unique_key` matches NULL to NULL, as dbt's default merge does. Composite keys
use plain equality.

## Capability checks

The adapter asks the server once per connection target whether it accepts `MERGE` and
`WITH RECURSIVE`, and caches the answer. `merge` uses `MERGE` as soon as the server accepts it,
with the same results.

## Recursive CTEs

dbt never generates recursive SQL, so this only matters for a model you write with
`WITH RECURSIVE` yourself, typically to walk a hierarchy. Recursive CTEs need an IRIS release
that supports them. On a server that does not, the model fails before it runs, with a message
naming the IRIS version.

Until then, when the maximum depth is known, unroll the hierarchy into one join per level. This
model returns every node below node 1 with its depth, up to `max_depth` levels, on any IRIS:

```sql
{{ config(materialized='table') }}
{% set max_depth = 3 %}
{% for depth in range(1, max_depth + 1) %}
select e{{ depth }}.child as node, {{ depth }} as depth
from {{ ref('edges') }} e1
{% for level in range(2, depth + 1) %}
join {{ ref('edges') }} e{{ level }} on e{{ level }}.parent = e{{ level - 1 }}.child
{% endfor %}
where e1.parent = 1
{% if not loop.last %}union all{% endif %}
{% endfor %}
```

It gives the same rows as the recursive form for hierarchies up to `max_depth` deep. Deeper
nodes are left out, so set `max_depth` to at least the deepest level you have. For hierarchies of
unknown depth, a Python model can walk the tree instead.

## Seeds

IRIS string columns compare without regard to case by default: `'female' = 'Female'` is true,
and `GROUP BY` returns the upper-case form (`'FEMALE'`). For seeds, `iris_collation` chooses:

| `iris_collation`   | Seed string columns                                              |
| ------------------ | ---------------------------------------------------------------- |
| not set, `default` | IRIS default: case-insensitive comparison, upper-case `GROUP BY` |
| `exact`            | Keep their case in `GROUP BY` and compare case-sensitively       |

Tables and views built from the seed inherit the collation. Any other value fails the seed
before it is created.

```yaml
seeds:
  my_project:
    +iris_collation: exact
```

On every IRIS build tested, a view that groups by an `exact` column fails with SQLCODE -400 when
it is used in `EXCEPT` or in a correlated `NOT EXISTS`. dbt's own data tests use neither.

## Snapshots

Snapshots support the `check` and `timestamp` strategies, a multi-column `unique_key`,
`snapshot_meta_column_names`, `dbt_valid_to_current` and all three `hard_deletes` modes.

They use a `HASH` SQL function written in ObjectScript, so they need no Embedded Python on the
server. It returns the same values as earlier dbt-iris releases, so existing snapshot history
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

The adapter refuses this one, because IRIS accepts it and stores wrong values:

- A `UNION` that gives a column a `DATE` or `TIME` in one branch and text, a number or the other
  of the two in another. A table built from it holds the date's internal day number
  (`'66154'` for 2022-02-14) or the time's seconds (`'36672'`), with no error. Before it builds a
  `table` or `incremental` model, the adapter reads each branch's column types and fails the model
  with a message naming the column. Cast the column to one type in every branch. A `NULL` branch
  is fine. The check does not see `POSIXTIME` columns, or a `UNION` whose branches cannot run on
  their own, such as one inside a correlated subquery.

## Running dbt more than once at a time

Temporary, intermediate and backup tables carry the invocation id, so overlapping `dbt run`
processes do not collide on them, and DDL that meets another process's lock is retried. Two
runs that replace the same models at the same time can still block each other on IRIS class
locks, and can damage the IRIS catalog. dbt does not support overlapping runs of one project: do not start a
second `dbt run` on the same models while one is running.
