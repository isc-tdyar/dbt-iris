"""IRIS translation of dbt-tests-adapter 1.20 simple_snapshot fixtures.

Same tables, rows and expected snapshot state as upstream (fixtures.py, new_record_*.py and
test_ephemeral_snapshot_hard_deletes.py), written in SQL that IRIS accepts:

- ``{schema}.t`` instead of ``{database}.{schema}.t``: IRIS has no three-part names.
- ``INSERT ... SELECT ... UNION ALL SELECT ...`` instead of a multi-row ``VALUES`` list.
- ``TIMESTAMP`` instead of ``TIMESTAMP WITHOUT TIME ZONE``, ``VARCHAR`` instead of ``TEXT``
  (IRIS's TEXT is a stream column, which cannot be compared).
- ``cast(null as timestamp)`` instead of ``null::timestamp``.
- ``dateadd('hour', 1, x)`` instead of ``x + interval '1 hour'``.
- The expected ``*_scd_id`` is computed exactly as the adapter's ``iris__snapshot_hash_arguments``
  computes ``dbt_scd_id`` (IRIS has no md5()); see ``scd_id``.

``{schema}`` is left in the SQL for dbt's run_sql (or the test) to format. Templates are filled
with str.replace on ``<name>`` markers, not f-strings: the repo's flake8 misreads multi-line
f-strings on Python 3.12.
"""

# fmt: off
SEED_COLUMNS = ("id", "first_name", "last_name", "email", "gender", "ip_address", "updated_at")
SEED_ROWS = [
    (1, "Judith", "Kennedy", "(not provided)", "Female", "54.60.24.128", "2015-12-24 12:19:28"),
    (2, "Arthur", "Kelly", "(not provided)", "Male", "62.56.24.215", "2015-10-28 16:22:15"),
    (3, "Rachel", "Moreno", "rmoreno2@msu.edu", "Female", "31.222.249.23", "2016-04-05 02:05:30"),
    (4, "Ralph", "Turner", "rturner3@hp.com", "Male", "157.83.76.114", "2016-08-08 00:06:51"),
    (5, "Laura", "Gonzales", "lgonzales4@howstuffworks.com", "Female", "30.54.105.168", "2016-09-01 08:25:38"),  # noqa: E501
    (6, "Katherine", "Lopez", "klopez5@yahoo.co.jp", "Female", "169.138.46.89", "2016-08-30 18:52:11"),
    (7, "Jeremy", "Hamilton", "jhamilton6@mozilla.org", "Male", "231.189.13.133", "2016-07-17 02:09:46"),
    (8, "Heather", "Rose", "hrose7@goodreads.com", "Female", "87.165.201.65", "2015-12-29 22:03:56"),
    (9, "Gregory", "Kelly", "gkelly8@trellian.com", "Male", "154.209.99.7", "2016-03-24 21:18:16"),
    (10, "Rachel", "Lopez", "rlopez9@themeforest.net", "Female", "237.165.82.71", "2016-08-20 15:44:49"),
    (11, "Donna", "Welch", "dwelcha@shutterfly.com", "Female", "103.33.110.138", "2016-02-27 01:41:48"),
    (12, "Russell", "Lawrence", "rlawrenceb@qq.com", "Male", "189.115.73.4", "2016-06-11 03:07:09"),
    (13, "Michelle", "Montgomery", "mmontgomeryc@scientificamerican.com", "Female", "243.220.95.82", "2016-06-18 16:27:19"),  # noqa: E501
    (14, "Walter", "Castillo", "wcastillod@pagesperso-orange.fr", "Male", "71.159.238.196", "2016-10-06 01:55:44"),  # noqa: E501
    (15, "Robin", "Mills", "rmillse@vkontakte.ru", "Female", "172.190.5.50", "2016-10-31 11:41:21"),
    (16, "Raymond", "Holmes", "rholmesf@usgs.gov", "Male", "148.153.166.95", "2016-10-03 08:16:38"),
    (17, "Gary", "Bishop", "gbishopg@plala.or.jp", "Male", "161.108.182.13", "2016-08-29 19:35:20"),
    (18, "Anna", "Riley", "arileyh@nasa.gov", "Female", "253.31.108.22", "2015-12-11 04:34:27"),
    (19, "Sarah", "Knight", "sknighti@foxnews.com", "Female", "222.220.3.177", "2016-09-26 00:49:06"),
    (20, "Phyllis", "Fox", None, "Female", "163.191.232.95", "2016-08-21 10:35:19"),
]
# fmt: on

# The multi-key seed: the same rows with id2 = 100 * id1.
MULTI_KEY_SEED_COLUMNS = ("id1", "id2") + SEED_COLUMNS[1:]
MULTI_KEY_SEED_ROWS = [(row[0], row[0] * 100) + row[1:] for row in SEED_ROWS]


def _literal(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def insert_rows(table: str, columns, rows) -> str:
    """One INSERT for several rows; IRIS has no multi-row VALUES list."""
    selects = "\nunion all ".join("select " + ", ".join(_literal(v) for v in row) for row in rows)
    return "insert into {schema}." + table + " (" + ", ".join(columns) + ")\n" + selects


def scd_id(*args: str) -> str:
    """The adapter's dbt_scd_id expression (iris__snapshot_hash_arguments) over SQL args."""
    parts = " || '|' || ".join("coalesce(cast(" + a + " as varchar(50)), '')" for a in args)
    return "HASH('md5', " + parts + ")"


# test_various_configs.py fixtures

create_seed_sql = """
create table {schema}.seed (
    id INTEGER,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    email VARCHAR(50),
    gender VARCHAR(50),
    ip_address VARCHAR(20),
    updated_at TIMESTAMP
)
"""

create_snapshot_expected_sql = """
create table {schema}.snapshot_expected (
    id INTEGER,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    email VARCHAR(50),
    gender VARCHAR(50),
    ip_address VARCHAR(20),
    updated_at TIMESTAMP,
    test_valid_from TIMESTAMP,
    TEST_VALID_TO   TIMESTAMP,
    test_scd_id     VARCHAR(1024),
    test_updated_at TIMESTAMP
)
"""

# Two users share an email, to check that duplicated check_cols values are handled.
seed_insert_sql = insert_rows("seed", SEED_COLUMNS, SEED_ROWS)

_EXPECTED_COLUMNS = """
    id,
    first_name,
    last_name,
    email,
    gender,
    ip_address,
    updated_at,
    test_valid_from,
    TEST_VALID_TO,
    test_updated_at,
    test_scd_id
"""

_SCD_ID = scd_id("id || '-' || first_name", "updated_at")


def _populate_expected(valid_to: str, where: str = "") -> str:
    return (
        """
insert into {schema}.snapshot_expected (<_EXPECTED_COLUMNS>)
select
    id,
    first_name,
    last_name,
    email,
    gender,
    ip_address,
    updated_at,
    updated_at as test_valid_from,
    <valid_to> as TEST_VALID_TO,
    updated_at as test_updated_at,
    <_SCD_ID> as test_scd_id
from {schema}.seed
<where>
""".replace(
            "<_EXPECTED_COLUMNS>", _EXPECTED_COLUMNS
        )
        .replace("<_SCD_ID>", _SCD_ID)
        .replace("<valid_to>", valid_to)
        .replace("<where>", where)
    )


populate_snapshot_expected_sql = _populate_expected("cast(null as timestamp)")
populate_snapshot_expected_valid_to_current_sql = _populate_expected("date('2099-12-31')")

snapshot_actual_sql = """
{% snapshot snapshot_actual %}

    {{
        config(
            unique_key='id || ' ~ "'-'" ~ ' || first_name',
        )
    }}

    select * from {{target.schema}}.seed

{% endsnapshot %}
"""

# Change email and updated_at of records 10 - 20, and close out their expected snapshot rows.
invalidate_sql = """
update {schema}.seed set
    updated_at = dateadd('hour', 1, updated_at),
    email      =  case when id = 20 then 'pfoxj@creativecommons.org' else 'new_' || email end
where id >= 10 and id <= 20;

update {schema}.snapshot_expected set
    TEST_VALID_TO   = dateadd('hour', 1, updated_at)
where id >= 10 and id <= 20
"""

# Insert v2 of records 10 - 20.
update_sql = _populate_expected("cast(null as timestamp)", "where id >= 10 and id <= 20")
update_with_current_sql = _populate_expected("date('2099-12-31')", "where id >= 10 and id <= 20")

# multi-key snapshot fixtures

create_multi_key_seed_sql = """
create table {schema}.seed (
    id1 INTEGER,
    id2 INTEGER,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    email VARCHAR(50),
    gender VARCHAR(50),
    ip_address VARCHAR(20),
    updated_at TIMESTAMP
)
"""

create_multi_key_snapshot_expected_sql = """
create table {schema}.snapshot_expected (
    id1 INTEGER,
    id2 INTEGER,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    email VARCHAR(50),
    gender VARCHAR(50),
    ip_address VARCHAR(20),
    updated_at TIMESTAMP,
    test_valid_from TIMESTAMP,
    TEST_VALID_TO   TIMESTAMP,
    test_scd_id     VARCHAR(1024),
    test_updated_at TIMESTAMP
)
"""

seed_multi_key_insert_sql = insert_rows("seed", MULTI_KEY_SEED_COLUMNS, MULTI_KEY_SEED_ROWS)

_MULTI_KEY_SCD_ID = scd_id("id1", "id2", "updated_at")


def _populate_multi_key_expected(where: str = "") -> str:
    return """
insert into {schema}.snapshot_expected (
    id1,
    id2,
    first_name,
    last_name,
    email,
    gender,
    ip_address,
    updated_at,
    test_valid_from,
    TEST_VALID_TO,
    test_updated_at,
    test_scd_id
)
select
    id1,
    id2,
    first_name,
    last_name,
    email,
    gender,
    ip_address,
    updated_at,
    updated_at as test_valid_from,
    cast(null as timestamp) as TEST_VALID_TO,
    updated_at as test_updated_at,
    <_MULTI_KEY_SCD_ID> as test_scd_id
from {schema}.seed
<where>
""".replace(
        "<_MULTI_KEY_SCD_ID>", _MULTI_KEY_SCD_ID
    ).replace(
        "<where>", where
    )


populate_multi_key_snapshot_expected_sql = _populate_multi_key_expected()

model_seed_sql = """
select * from {{target.schema}}.seed
"""

invalidate_multi_key_sql = """
update {schema}.seed set
    updated_at = dateadd('hour', 1, updated_at),
    email      =  case when id1 = 20 then 'pfoxj@creativecommons.org' else 'new_' || email end
where id1 >= 10 and id1 <= 20;

update {schema}.snapshot_expected set
    TEST_VALID_TO   = dateadd('hour', 1, updated_at)
where id1 >= 10 and id1 <= 20
"""

update_multi_key_sql = _populate_multi_key_expected("where id1 >= 10 and id1 <= 20")


# new_record_timestamp_mode.py (also used by new_record_check_mode.py) fixtures


def _populate_new_record_expected(where: str = "") -> str:
    return """
insert into {schema}.snapshot_expected (
    id,
    first_name,
    last_name,
    email,
    gender,
    ip_address,
    updated_at,
    dbt_valid_from,
    dbt_valid_to,
    dbt_updated_at,
    dbt_scd_id,
    dbt_is_deleted
)
select
    id,
    first_name,
    last_name,
    email,
    gender,
    ip_address,
    updated_at,
    updated_at as dbt_valid_from,
    cast(null as timestamp) as dbt_valid_to,
    updated_at as dbt_updated_at,
    <_SCD_ID> as dbt_scd_id,
    'False' as dbt_is_deleted
from {schema}.seed
<where>
""".replace(
        "<_SCD_ID>", _SCD_ID
    ).replace(
        "<where>", where
    )


seed_new_record_mode_statements = [
    """create table {schema}.seed (
    id INTEGER,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    email VARCHAR(50),
    gender VARCHAR(50),
    ip_address VARCHAR(20),
    updated_at TIMESTAMP)""",
    """create table {schema}.snapshot_expected (
    id INTEGER,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    email VARCHAR(50),
    gender VARCHAR(50),
    ip_address VARCHAR(20),
    updated_at TIMESTAMP,
    dbt_valid_from TIMESTAMP,
    dbt_valid_to   TIMESTAMP,
    dbt_scd_id     VARCHAR(1024),
    dbt_updated_at TIMESTAMP,
    dbt_is_deleted VARCHAR(50)
    )""",
    seed_insert_sql,
    _populate_new_record_expected(),
]

new_record_snapshot_actual_sql = snapshot_actual_sql

new_record_invalidate_sql_statements = [
    """update {schema}.seed set
    updated_at = dateadd('hour', 1, updated_at),
    email      =  case when id = 20 then 'pfoxj@creativecommons.org' else 'new_' || email end
where id >= 10 and id <= 20""",
    """update {schema}.snapshot_expected set
    dbt_valid_to   = dateadd('hour', 1, updated_at)
where id >= 10 and id <= 20""",
]

new_record_update_sql = _populate_new_record_expected("where id >= 10 and id <= 20")

new_record_delete_sql = """
delete from {schema}.seed where id = 1
"""

new_record_reinsert_sql = insert_rows(
    "seed",
    SEED_COLUMNS,
    [(1, "Judith", "Kennedy", "(not provided)", "Female", "54.60.24.128", "2200-01-01 12:00:00")],
)


# new_record_dbt_valid_to_current.py fixtures

valid_to_current_seed_statements = [
    "create table {schema}.seed (id INTEGER, first_name VARCHAR(50))",
    insert_rows("seed", ("id", "first_name"), [(1, "Judith"), (2, "Arthur")]),
]

valid_to_current_snapshot_actual_sql = """
{% snapshot snapshot_actual %}
    select * from {{target.schema}}.seed
{% endsnapshot %}
"""

valid_to_current_delete_sql = new_record_delete_sql


# test_ephemeral_snapshot_hard_deletes.py fixtures

source_create_sql = """
create table {schema}.src_customers (
    id INTEGER,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    email VARCHAR(50),
    updated_at TIMESTAMP
)
"""

source_insert_sql = insert_rows(
    "src_customers",
    ("id", "first_name", "last_name", "email", "updated_at"),
    [
        (1, "John", "Doe", "john.doe@example.com", "2023-01-01 10:00:00"),
        (2, "Jane", "Smith", "jane.smith@example.com", "2023-01-02 11:00:00"),
        (3, "Bob", "Johnson", "bob.johnson@example.com", "2023-01-03 12:00:00"),
    ],
)

source_alter_sql = """
alter table {schema}.src_customers add column dummy_column VARCHAR(50) default 'dummy_value'
"""

source_delete_sql = """
delete from {schema}.src_customers where id = 3
"""
