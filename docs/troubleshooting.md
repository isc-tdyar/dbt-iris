# Troubleshooting

Each entry starts with the message you see, quoted as dbt or IRIS prints it, then says what causes
it and what to do. Search this page for a few words of your error. Messages that start with
`dbt-iris:` come from the adapter; the rest come from IRIS or its driver, `intersystems-irispython`.

## Installing and upgrading

### `AttributeError: module 'iris' has no attribute 'irissdk'`

**Cause.** You upgraded from dbt-iris 1.9.x with `pip install -U dbt-iris`. dbt-iris 1.9.x shipped
its own copy of the `iris` package. When pip removes 1.9.x, it deletes `iris/__init__.py`, which
now belongs to `intersystems-irispython`, the driver 2.0.0 depends on.

**Fix.** Reinstall the driver once:

```shell
python -m pip install --force-reinstall --no-deps intersystems-irispython
```

### `dbt-iris: the profile setting driver = 'vendored' was removed in dbt-iris 2.0.0`

The full message continues: "The adapter now connects only through intersystems-irispython
(iris.dbapi); remove the setting or set it to 'iris'." The same message names the environment
variable `DBT_IRIS_DRIVER` when that is where the value comes from.

**Cause.** dbt-iris 1.9.x let you choose between its bundled driver and SQLAlchemy. 2.0.0 has one
driver.

**Fix.** Delete `driver:` from the profile and unset `DBT_IRIS_DRIVER`.

### `WARNING:_iris_ep._runtime_facade:IRISINSTALLDIR or ISC_PACKAGE_INSTALLDIR environment variable is not set`

It comes with a second line, `WARNING:_iris_ep._runtime_facade:Embedded Python not configured;
call iris.connect(path=...) to configure it`, near the start of every dbt command.

**Cause.** `intersystems-irispython` 5.4.1 looks for a local IRIS installation when it loads, for
Embedded Python. dbt connects over the network and does not need one.

**Fix.** None needed: the run is not affected.

## Connecting

All connection failures reach dbt as `Database Error` followed by the driver's message. Measured
with `intersystems-irispython` 5.4.1 against IRIS 2026.2.

### `Failed to connect to server; Details: <COMMUNICATION ERROR> Invalid Message received; Details: Access Denied`

**Cause.** IRIS refused the login. The driver gives this same message for three different
problems:

- a wrong password,
- a user that does not exist,
- a namespace (the profile's `database`) that does not exist or that the user may not use.

**Fix.** Check `username`, `password` and `database` in the profile. In the Management Portal,
**System Administration > Security > Users** shows the user and its roles, and
**System Administration > Configuration > System Configuration > Namespaces** lists the
namespaces. The server's `%Service_Bindings` service must also allow password authentication
(**System Administration > Security > Services**).

### `Failed to connect to server; Details: <COMMUNICATION ERROR> Invalid Message received; Details: Password change required`

**Cause.** The user's password has expired, or the user was created with "change password on
next login". New IRIS containers start with every predefined user's password expired.

**Fix.** Change the password in the Management Portal or a terminal session, or, for a local test
container, unexpire them all:

```shell
docker exec -it <container> iris session IRIS -U %SYS \
  '##class(Security.Users).UnExpireUserPasswords("*")'
```

### `Failed to connect to server; Details: Error code: -1 Error message:`

**Cause.** Nothing answered on that host and port: the wrong `port`, IRIS not running, or a
firewall in between. The superserver port is usually 1972; 52773 is the web port, which dbt does
not use.

**Fix.** Check `port`, and that IRIS is up (`iris list` on the server, or `docker ps` for a
container).

### `Failed to connect to server; Details: Error code: -2 Error message: getaddrinfo(...) failed in s_TCPConnect, reason = Name or service not known.`

**Cause.** The `hostname` does not resolve.

**Fix.** Check `hostname`. From inside a container, `localhost` is the container itself, not the
machine running it.

## Building models

### `This IRIS server (IRIS ...) does not accept WITH RECURSIVE (recursive common table expressions), and this model uses one.`

The message goes on: "Rewrite the model without recursion (see "Recursive CTEs" in the dbt-iris
docs for a pattern), or run it on an IRIS release that supports recursive CTEs."

**Cause.** The model uses `WITH RECURSIVE`, and the connected IRIS release does not support
recursive CTEs. The adapter asks the server once and refuses the model before sending it. dbt
itself never writes recursive SQL, so this is always SQL from your project.

**Fix.** When the depth of the hierarchy is known, unroll it into one join per level; the
[configs page](dbt-docs-site/iris-configs.md#recursive-ctes) has a pattern that works on any IRIS.
For a hierarchy of unknown depth, walk it in a Python model.

### `dbt-iris: Column 'visited' is DATE in one UNION branch and VARCHAR in another.`

The message goes on: "When IRIS builds a table from this UNION it stores the DATE values as
internal day numbers (for example '66154' for 2022-02-14), and raises no error. Give the column the
same type in every branch, for example cast('2022-02-15' as date) instead of '2022-02-15'." A
`TIME` column gets the same message with seconds since midnight (`'36672'`).

**Cause.** IRIS stores wrong values when it builds a table from a `UNION` that mixes a `DATE` or
`TIME` with another type in one column. A plain query of the same `UNION` looks right, so the
adapter checks each branch before a `table` or `incremental` model is built, and stops.

**Fix.** Cast the column to one type in every branch. A branch that is just `NULL` is fine. See
[IRIS SQL differences](iris-sql.md).

### A table shows `'66154'` where a date should be

**Cause.** The same IRIS behaviour as the entry above, in a table built before dbt-iris 2.0.0's
check, built outside dbt, or from a column the check cannot see (`POSIXTIME`, or a `UNION` whose
branches cannot run on their own).

**Fix.** Cast every branch of the `UNION` to the same type, and rebuild the model with
`dbt run --full-refresh --select <model>`.

### `iris_materialized_view_as must be one of 'table', 'view', got '...'`

**Cause.** A `materialized_view` model has an `iris_materialized_view_as` value other than `table`
or `view`. The model fails before any SQL runs.

**Fix.** Use `table` or `view`, or remove the setting. See
[configuration](configuration.md#iris_materialized_view_as).

### `dbt-iris: IRIS has no materialized views. These materialized_view models are built as tables and rebuilt on every dbt run: ...`

A warning, not an error.

**Cause.** The project has `materialized_view` models with no `iris_materialized_view_as` setting.
They are built as tables. The warning appears once per run and lists them.

**Fix.** Nothing is wrong. To silence it, set `iris_materialized_view_as: table` to keep the
tables, or `view` to build views instead. For a large model that is rebuilt often,
`materialized='incremental'` is cheaper.

### `iris_collation must be one of 'default', 'exact', got ...`

**Cause.** A seed's `iris_collation` is neither `default` nor `exact`. The seed fails before its
table is created.

**Fix.** Use `default` or `exact`. See [configuration](configuration.md#seeds).

### `GROUP BY` returns `'FEMALE'` where the data says `'Female'`

**Cause.** IRIS string columns default to a case-insensitive collation. `GROUP BY` and `DISTINCT`
return the upper-case form, and `'female' = 'Female'` is true.

**Fix.** Group by `%EXACT(column)` to keep the stored case. For seeds, set
`iris_collation: exact`, which makes their string columns keep case and compare case-sensitively,
as other warehouses do.

### An aggregate model returns one row where it should return many

**Cause.** The model groups with a column number, `group by 1` (or `dbt_utils.group_by(n)`, which
writes that). IRIS reads a number in `GROUP BY` as a constant, so every row falls into one group.
There is no error.

**Fix.** Name the columns in `GROUP BY`, or repeat their expressions. `ORDER BY 1` is fine. See
[IRIS SQL differences](iris-sql.md#group-by-1-groups-by-the-number-1).

## Snapshots and Python models

### Could not install the HASH() SQL function

The warning reads: "dbt-iris: could not install the HASH() SQL function that snapshots use: this
IRIS user may not create functions with ObjectScript code. SQL models, seeds and tests run;
snapshots and Python models need a user with the %Developer role (for snapshots, HASH() installed
once by such a user is enough)."

**Cause.** When dbt creates a schema, the adapter installs a `HASH()` SQL function written in
ObjectScript, which snapshots use. IRIS refuses it to a user who has only SQL privileges:

```text
[SQLCODE: <-99>:<Privilege violation>]
[%msg: <User dbt does not have privilege to CREATE FUNCTION with custom code>]
```

SQL models, seeds and tests are unaffected. A snapshot then fails because `HASH()` does not exist.

**Fix.** Give the dbt user the `%Developer` role. Or have a user with that role install the
function once, with the same profile but their own credentials:
`dbt run-operation create_function_hash`. The function stays installed for the namespace.

### `does not have privilege to CREATE PROCEDURE with custom code`

The full error is SQLCODE -99, `Privilege violation`, from a Python model.

**Cause.** A Python model runs as a stored procedure written in Python, which the adapter creates
for the run. IRIS allows `CREATE PROCEDURE` with code only to users who hold `%Developer` or an
equivalent role. Unlike `HASH()`, the procedure is created on every run, so installing it once
does not help.

**Fix.** Run Python models as a user with the `%Developer` role.

### Python models fail with `Missing required dependencies: sqlalchemy, sqlalchemy-iris`

`Missing required dependency: pandas` is the same problem.

**Cause.** Python models run in IRIS's own Python, on the server, not in the Python that runs dbt.

**Fix.** Install the packages into IRIS's Python on the server; see
[configuration](configuration.md#python-models).

## Errors that come from IRIS itself

### `<PARAMETER ERROR>; Details: Invalid number of parameters.`

**Cause.** On IRIS 2026.3, for a user with `%All` (such as `_SYSTEM` or `SuperUser`): after one
connection adds a column to a table, a new connection that runs a statement IRIS had already
cached for that table fails, although the statement has no parameters. dbt-iris clears the table's
cached queries after every column change it makes (`on_schema_change`, snapshots, column type
changes), so dbt runs no longer hit this. You can still meet it in your own SQL after your own
`ALTER TABLE`, in a hook or outside dbt.

**Fix.** Run the statement with different text (a different column alias is enough), run
`PURGE CACHED QUERIES BY TABLE "schema"."table"` from a connection other than the one that ran the
`ALTER`, or connect as a user without `%All`. IRIS 2026.1 and 2026.2 are not affected.

### `ERROR #5864` while two dbt runs are going

The same situation can also give `ERROR #5351` (class does not exist), `ERROR #5116` (class
dictionary version out of date), a model that cannot find a view another run is replacing, or,
later, SQLCODE -300 `DDL not enabled for class` when the schema is dropped.

**Cause.** Two `dbt run` processes replaced the same views or tables at the same time. IRIS keeps
each table and view as a class, and two processes cannot change one class at once. The adapter
retries a statement that meets another process's class lock, but cannot make two runs replace one
model safely. A collision can leave a view's class damaged.

**Fix.** Do not overlap runs of the same models: dbt does not support it on any warehouse. Run one
`dbt run` at a time per target, or give concurrent runs different targets (`schema`). If a schema
can no longer be dropped after a collision, the damaged view's class needs repair by an IRIS
administrator before the schema can be dropped.
