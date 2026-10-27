# dbt Fusion (preview)

dbt Fusion is the dbt engine that replaces dbt-core. It does not load a Python adapter such as
dbt-iris. dbt-iris 2.0.0 works with dbt-core; this page says what it already does for dbt Fusion,
and what is still missing.

## What is in dbt-iris 2.0.0

dbt Fusion runs the adapter's SQL macros directly, without the Python code dbt-core uses. Two
changes make dbt-iris's macros work on their own:

- **Schemas.** Creating a schema (which installs the `HASH()` function snapshots use) and
  checking whether a schema exists are SQL macros, not only Python methods.
- **Seeds.** Under dbt Fusion a seed is loaded through `adapter.load_dataframe`, instead of
  batched `INSERT`s. dbt-core keeps the batched `INSERT`s.

The seed path is chosen by dbt's version, and dbt-core never runs the schema macros because the
adapter's Python methods do that work, so dbt-core runs exactly as before.

## What is missing

Using dbt Fusion with IRIS needs an IRIS adapter built for dbt Fusion, and **it is not published
yet**. Until it is, use dbt-iris with dbt-core.

## What will differ under dbt Fusion

These dbt-iris features run in the adapter's Python code, which dbt Fusion does not load:

- the check that refuses a `UNION` mixing `DATE` or `TIME` with another type;
- the cached-query purge after a column change;
- the warning when `HASH()` cannot be installed.

They will need an equivalent in the dbt Fusion adapter.
