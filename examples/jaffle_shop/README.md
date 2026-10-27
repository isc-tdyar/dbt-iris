# jaffle_shop on InterSystems IRIS

A small dbt project for a fictional shop, used by the
[dbt-iris tutorial](../../docs/tutorial.md). It is dbt's classic jaffle_shop: three seed files of
customers, orders and payments, staging views over them, and two tables built from those. It adds
one incremental model and one snapshot so you can watch both change on a second run.

| Kind        | Name                                          | What it shows                                             |
| ----------- | --------------------------------------------- | --------------------------------------------------------- |
| Seeds       | `raw_customers`, `raw_orders`, `raw_payments` | CSV files loaded into IRIS tables                         |
| Views       | `stg_customers`, `stg_orders`, `stg_payments` | Renamed columns, amounts in dollars                       |
| Tables      | `customers`, `orders`                         | Joins, aggregates and a Jinja loop over payment methods   |
| Incremental | `order_status_history`                        | Later runs add only orders newer than the newest one kept |
| Snapshot    | `customers_snapshot`                          | Keeps every version of a customer row                     |
| Tests       | 20 data tests                                 | `unique`, `not_null`, `accepted_values`, `relationships`  |

The seeds set `iris_collation: exact`, so their text columns compare case-sensitively, as on
other warehouses.

## Run it

From the root of the dbt-iris repository, with IRIS running (`docker compose up -d`) and
`dbt-iris` installed:

```shell
dbt build --project-dir examples/jaffle_shop --profiles-dir examples/jaffle_shop
```

`profiles.yml` here connects to `localhost:1972` as `_SYSTEM` / `SYS` in the `USER` namespace and
builds into the `jaffle_shop` schema. Set `DBT_IRIS_HOST`, `DBT_IRIS_PORT`, `DBT_IRIS_USER` or
`DBT_IRIS_PASS` to point it elsewhere.

CI builds this project twice against IRIS Community on every change to the adapter.
