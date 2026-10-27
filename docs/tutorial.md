# Tutorial: a first dbt project on InterSystems IRIS

This walks you from nothing to a built and tested dbt project in IRIS.
You start IRIS in Docker, point dbt at it, build the example project in
[`examples/jaffle_shop`](../examples/jaffle_shop), look at the results in IRIS, then change some
data and watch an incremental model and a snapshot pick it up.

You need Docker, Python 3.10 or later and git. The output below was captured against IRIS
Community 2026.2 with dbt-core 1.12; timings and timestamps will differ on your machine.

## 1. Start IRIS

Clone the repository and start the IRIS Community container it defines:

```shell
git clone https://github.com/caretdev/dbt-iris.git
cd dbt-iris
docker compose up -d
```

The first start builds a small image on top of IRIS Community, adding the packages that Python
models need. IRIS is ready when `docker compose logs iris` shows
`...started InterSystems IRIS instance IRIS`. It listens on two ports:

- **1972**, the superserver, which dbt connects to.
- **52773**, the web server, with the Management Portal at
  [http://localhost:52773/csp/sys/UtilHome.csp](http://localhost:52773/csp/sys/UtilHome.csp).

The login is `_SYSTEM` / `SYS`. The compose file clears IRIS's "change your password on first
login" flag so that these defaults work.

## 2. Install dbt-iris

In a virtual environment:

```shell
python -m venv .venv
source .venv/bin/activate
python -m pip install dbt-core dbt-iris
```

`pip` also installs `intersystems-irispython`, the InterSystems driver that dbt-iris uses to talk
to IRIS. To try the adapter from this clone instead of from PyPI, run
`python -m pip install -e . dbt-core`.

## 3. Check the connection

The example project carries its own profile, `examples/jaffle_shop/profiles.yml`:

```yaml
jaffle_shop:
  target: dev
  outputs:
    dev:
      type: iris
      hostname: "{{ env_var('DBT_IRIS_HOST', 'localhost') }}"
      port: "{{ env_var('DBT_IRIS_PORT', '1972') | as_number }}"
      database: USER # the IRIS namespace
      username: "{{ env_var('DBT_IRIS_USER', '_SYSTEM') }}"
      password: "{{ env_var('DBT_IRIS_PASS', 'SYS') }}"
      schema: jaffle_shop
      threads: 4
```

Two settings mean something specific on IRIS. `database` is the IRIS **namespace**, here `USER`,
which every IRIS instance has. `schema` is the SQL schema the models are built in, the name before
the dot in `jaffle_shop.customers`. IRIS creates it with the first table. The
[overview](overview.md) has the full mapping.

Run `dbt debug` from the repository root:

```shell
dbt debug --project-dir examples/jaffle_shop --profiles-dir examples/jaffle_shop
```

```text
Connection:
  hostname: localhost
  database: USER
  schema: jaffle_shop
  Connection test: [OK connection ok]
All checks passed!
```

If the connection fails, [troubleshooting](troubleshooting.md) lists the usual causes. The rest of
this tutorial leaves out the two `--project-dir` and `--profiles-dir` flags for readability: add
them to every command, or `cd examples/jaffle_shop` and use `--profiles-dir .`.

## 4. Load the seeds

The project starts from three CSV files of customers, orders and payments. `dbt seed` creates a
table for each and loads it:

```shell
dbt seed
```

```text
1 of 3 OK loaded seed file jaffle_shop.raw_customers ........ [INSERT 100 in 0.20s]
2 of 3 OK loaded seed file jaffle_shop.raw_orders ........... [INSERT 99 in 0.20s]
3 of 3 OK loaded seed file jaffle_shop.raw_payments ......... [INSERT 113 in 0.20s]
Done. PASS=3 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=3
```

The project sets `iris_collation: exact` on its seeds. IRIS text columns ignore case by default,
so `'female' = 'Female'` is true and `GROUP BY` returns `'FEMALE'`. With `exact`, the seed
columns behave as they would on other warehouses. [IRIS SQL](iris-sql.md) explains the default.

## 5. Build and test everything

`dbt build` runs the seeds, models, snapshot and tests in dependency order:

```shell
dbt build
```

```text
6 of 30 OK created sql view model jaffle_shop.stg_customers ............ [SUCCESS 0 in 0.06s]
4 of 30 OK created sql view model jaffle_shop.stg_orders ............... [SUCCESS 0 in 0.09s]
5 of 30 OK created sql view model jaffle_shop.stg_payments ............. [SUCCESS 0 in 0.09s]
7 of 30 OK snapshotted jaffle_shop.customers_snapshot .................. [SUCCESS 100 in 0.23s]
16 of 30 OK created sql incremental model jaffle_shop.order_status_history [SUCCESS 99 in 0.11s]
17 of 30 OK created sql table model jaffle_shop.customers .............. [SUCCESS 100 in 0.25s]
18 of 30 OK created sql table model jaffle_shop.orders ................. [SUCCESS 99 in 0.25s]
28 of 30 PASS relationships_orders_customer_id__customer_id__ref_customers_ [PASS in 0.08s]
...
Done. PASS=30 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=30
```

Each materialization became an ordinary IRIS SQL object:

| Model                  | Materialization | In IRIS                                                      |
| ---------------------- | --------------- | ------------------------------------------------------------ |
| `stg_*`                | `view`          | A SQL view                                                   |
| `customers`, `orders`  | `table`         | A table built with `CREATE TABLE ... AS SELECT`              |
| `order_status_history` | `incremental`   | A table; later runs insert only the new rows                 |
| `customers_snapshot`   | snapshot        | A table with `dbt_valid_from` and `dbt_valid_to` per version |

The 20 tests are SQL queries that dbt runs against those objects; each passes when it returns no
rows.

## 6. Look at the results in IRIS

Open IRIS's SQL shell inside the container:

```shell
docker compose exec iris iris sql IRIS -U USER
```

Type `set selectmode odbc` first. The shell otherwise shows some date results, such as
`MAX(order_date)`, as IRIS's internal day numbers (`64748` for 2018-04-10); dbt itself always
reads dates as dates.

```sql
set selectmode odbc
SELECT TOP 5 customer_id, first_name, number_of_orders, customer_lifetime_value
FROM jaffle_shop.customers ORDER BY customer_lifetime_value DESC
```

```text
| customer_id | first_name | number_of_orders | customer_lifetime_value |
| -- | -- | -- | -- |
| 51 | Howard | 3 | 99 |
| 3 | Kathleen | 3 | 65 |
| 46 | Norma | 2 | 64 |
| 30 | Christina | 2 | 57 |
| 54 | Rose | 5 | 57 |
```

Type `quit` to leave the shell. The same queries work in the Management Portal under
**System Explorer > SQL**, with the namespace set to `USER`.

## 7. Change the data and run again

Make three changes to the seed files: rename customer 1, and add an order with its payment.

```shell
cd examples/jaffle_shop
sed -i.bak 's/^1,Michael,P\./1,Mike,P./' seeds/raw_customers.csv
echo '100,1,2018-04-10,placed' >> seeds/raw_orders.csv
echo '114,100,credit_card,1500' >> seeds/raw_payments.csv
dbt build --profiles-dir .
```

```text
1 of 30 OK loaded seed file jaffle_shop.raw_customers ........ [INSERT 100 in 0.14s]
2 of 30 OK loaded seed file jaffle_shop.raw_orders ........... [INSERT 100 in 0.13s]
3 of 30 OK loaded seed file jaffle_shop.raw_payments ......... [INSERT 114 in 0.13s]
16 of 30 OK created sql incremental model jaffle_shop.order_status_history [SUCCESS 1 in 0.37s]
7 of 30 OK snapshotted jaffle_shop.customers_snapshot ........ [SUCCESS 1 in 0.90s]
Done. PASS=30 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=30
```

The seeds reloaded in full, the incremental model inserted one row (the new order) instead of
rebuilding, and the snapshot recorded one changed customer. In the SQL shell:

```sql
set selectmode odbc
SELECT id, first_name, dbt_valid_from, dbt_valid_to
FROM jaffle_shop.customers_snapshot WHERE id = 1 ORDER BY dbt_valid_from
SELECT COUNT(*) AS orders_in_history, MAX(order_date) AS newest
FROM jaffle_shop.order_status_history
```

```text
| id | first_name | dbt_valid_from | dbt_valid_to |
| -- | -- | -- | -- |
| 1 | Michael | 2026-10-27 01:01:39.047311 | 2026-10-27 01:01:42.73653 |
| 1 | Mike | 2026-10-27 01:01:42.73653 |  |
| orders_in_history | newest |
| -- | -- |
| 100 | 2018-04-10 |
```

The old row for customer 1 now has an end time, and the current one has none.

If you add an order without a payment, five of the `not_null` tests on `orders` fail on the next
build, because the order's payment amounts are null. That is the tests doing their job.

## 8. See a guardrail

Some SQL runs on IRIS but stores wrong values. The adapter refuses the cases it can detect before
anything is written. Add this model as `models/mixed_dates.sql`:

```sql
{{ config(materialized='table') }}
select 1 as id, cast('2022-02-14' as date) as visited
union all select 2, '2022-02-15'
```

`dbt build --profiles-dir . --select mixed_dates` fails with:

```text
dbt-iris: Column 'visited' is DATE in one UNION branch and VARCHAR in another. When IRIS builds
a table from this UNION it stores the DATE values as internal day numbers (for example '66154'
for 2022-02-14), and raises no error. Give the column the same type in every branch, for
example cast('2022-02-15' as date) instead of '2022-02-15'.
```

Change `'2022-02-15'` to `cast('2022-02-15' as date)` and the model builds. [IRIS SQL](iris-sql.md)
lists the other places where IRIS SQL differs from other warehouses.

## 9. Clean up

Put the seed files back and delete the extra model:

```shell
git checkout -- seeds
rm -f seeds/*.bak models/mixed_dates.sql
cd ../..
```

`docker compose down` stops IRIS and removes the container, with everything dbt built in it.

## Next

- [Overview](overview.md): how dbt-iris works and how dbt's names map to IRIS.
- [Configuration](configuration.md): every profile setting and model config.
- [IRIS SQL](iris-sql.md): where IRIS SQL differs, with examples.
- [Troubleshooting](troubleshooting.md): error messages and their fixes.
- [dbt Fusion](fusion.md) and [contributing](contributing.md).
