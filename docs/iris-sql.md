# IRIS SQL differences

dbt models are SQL, and IRIS SQL differs from PostgreSQL, Snowflake or BigQuery SQL in places a
dbt user meets quickly. This page lists those places, measured on IRIS 2026.1, 2026.2 and 2026.3
through `intersystems-irispython` 5.4.1, the driver dbt-iris uses. Three of them can give wrong
results without an error; they come first.

## Silent wrong results

### `GROUP BY 1` groups by the number 1

IRIS reads a number in `GROUP BY` as a constant, not as a column position, so every row falls
into one group and no error is raised:

```sql
select status, count(*) from orders group by 1      -- one row, the count of all orders
select status, count(*) from orders group by status -- one row per status
```

In a list with named columns the number is ignored: `group by 1, city` groups by `city` alone, and
the first column's value comes from an arbitrary row of each group. The IRIS SQL reference
documents this ("You cannot specify a field by column number; this is interpreted as a literal and
returns one row").

dbt-iris refuses any statement with a number in `GROUP BY`, with a message, instead of letting it
return wrong results. Name the columns (or repeat the expressions) in `GROUP BY`.
`dbt_utils.group_by(n)` generates `group by 1, 2, ...`, so do not use it on IRIS. `ORDER BY 1` does
sort by the first column.

### A `UNION` that mixes `DATE` or `TIME` with another type

When one branch of a `UNION` has a `DATE` and another has text or a number in the same column, a
plain query returns the right values, but a table built from it stores the date's internal day
number (`'66154'` for 2022-02-14). `TIME` values are stored as seconds (`'36672'`), and `DATE`
with `TIME` stores the time as a date. dbt-iris checks each branch before it builds a `table` or
`incremental` model and fails the model with a message naming the column, so this shows up as an
error, not as wrong data. Give the column one type in every branch:

```sql
select cast('2022-02-14' as date) as visited
union all
select cast('2022-02-15' as date)   -- not '2022-02-15'
```

A `NULL` branch is fine, and so is `DATE` with `TIMESTAMP`. The check cannot see `POSIXTIME`
columns, or a `UNION` whose branches cannot run on their own (one inside a correlated subquery).
A view built from such a `UNION` reads correctly.

### Strings compare without regard to case

By default IRIS compares strings case-insensitively: `'female' = 'Female'` is true, `LIKE 'A'`
matches `'a'`, and `GROUP BY` returns the upper-case form (`'FEMALE'`). To keep case:

- wrap the column in `%EXACT()` where you compare or group: `group by %exact(gender)`;
- or, for seeds, set `iris_collation: exact` (see [Configuration](configuration.md)), which makes
  the seed's string columns, and the tables built from them, case-sensitive.

A view that groups by an `exact` column fails with SQLCODE -400 when it is used in `EXCEPT` or in
a correlated `NOT EXISTS`; joins, `IN`, `NOT IN` and dbt's data tests work.

## Syntax IRIS does not accept, and what to write instead

| You may write                    | On IRIS                                                          | Write instead                                                                |
| -------------------------------- | ---------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| `extract(year from d)`           | Not accepted (SQLCODE -12)                                       | `year(d)`, `datepart('yyyy', d)` or `{fn year(d)}`                           |
| `d + interval '1' day`           | Not accepted                                                     | `dateadd('day', 1, d)`                                                       |
| `true`, `false`                  | Not accepted as literals                                         | `1` and `0` (IRIS booleans are `BIT`)                                        |
| `select a > b as flag`           | Not accepted in a select list                                    | `case when a > b then 1 else 0 end as flag`                                  |
| `x::varchar`                     | Not accepted                                                     | `cast(x as varchar(20))`                                                     |
| `ilike`                          | Not accepted (SQLCODE -14)                                       | `like`, which is already case-insensitive by default                         |
| `order by x nulls last`          | Not accepted                                                     | `order by case when x is null then 1 else 0 end, x`                          |
| `a is distinct from b`           | Not accepted                                                     | `(a <> b or (a is null and b is not null) or (a is not null and b is null))` |
| `qualify ...`                    | Not accepted                                                     | Filter the window function in an outer query                                 |
| `count(*) filter (where ...)`    | Not accepted                                                     | `sum(case when ... then 1 else 0 end)`                                       |
| `string_agg(s, ',')`, `listagg`  | No such function (SQLCODE -359)                                  | `list(s)`, which returns a comma-separated list                              |
| `insert ... values (...), (...)` | Only one row per `VALUES`                                        | `insert ... select ... union all select ...`                                 |
| `merge into ...`                 | Not accepted on any release yet                                  | The `merge` strategy works without it                                        |
| `with recursive ...`             | Not accepted on any release yet                                  | A fixed-depth join, below                                                    |
| `json_object('k': v)`            | Fails through the Python driver, which reads `:v` as a parameter | Build JSON in a Python model, or with string functions                       |

These work as on other warehouses: `limit n` (and `top n`), `offset ... fetch next ...`, `||`,
`concat()`, `coalesce`, `nullif`, `ifnull`, `nvl`, `greatest`, `least`, `case`, window functions
(`row_number() over (...)`, `sum(...) over (partition by ...)`), `count(distinct ...)`, `except`,
`intersect`, `cross join lateral`, `exists`, ordinary CTEs, `cast(... as date)` from ISO text,
`current_date`, `current_timestamp(6)`, `dateadd`, `datediff`, `date_trunc`, double-quoted
identifiers and `''` inside string literals.

`date_trunc` returns text on 2026.1 and 2026.2, and a `TIMESTAMP` on 2026.3. Cast it if a later
step needs one type.

## What the adapter rewrites or emulates for you

You do not need to change SQL for these; they are listed so that the SQL you see in IRIS's logs
makes sense.

- **A `WITH` clause inside a subquery** (a derived table, `IN (...)`, a `UNION` branch or a scalar
  subquery), **or one CTE nested inside another** (an ephemeral model that has its own CTEs). IRIS
  accepts neither, so the adapter moves the CTEs to the statement's top-level `WITH`. If a moved
  CTE's name is already used there, the statement is sent as written and IRIS's error shows.
- **`merge`** runs as `UPDATE ... FROM` for matched rows and `INSERT ... WHERE NOT EXISTS` for new
  ones, and switches to `MERGE` on a server that accepts it.
- **Seeds** load with batched single-row inserts.
- **Renaming a view** drops and recreates it, because IRIS has no `ALTER VIEW ... RENAME`.
- **Materialized views** are built as tables rebuilt on every run (or as views); IRIS has none.

## Recursive CTEs

No IRIS release accepts `WITH RECURSIVE` yet. A model that uses one fails before it runs, with a
message naming the IRIS version. When the maximum depth is known, unroll the hierarchy into one
join per level; the [configs page](dbt-docs-site/iris-configs.md#recursive-ctes) has a model that
returns the same rows as the recursive form.

## Names

- IRIS keeps a table's name as it was written (`MixedCase` in the catalog) and matches it in any
  case, quoted or not: `orders`, `Orders` and `"ORDERS"` are the same table.
- The SQL schema is the part before the dot. A namespace (the profile's `database`) is not part
  of a table's name; a connection works in one namespace.
