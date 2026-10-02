<p align="center">
  <img src="https://raw.githubusercontent.com/dbt-labs/dbt/ec7dee39f793aa4f7dd3dae37282cc87664813e4/etc/dbt-logo-full.svg" alt="dbt logo" width="500"/>
</p>

**[dbt](https://www.getdbt.com/)** enables data analysts and engineers to transform their data using the same practices that software engineers use to build applications.

dbt is the T in ELT. Organize, cleanse, denormalize, filter, rename, and pre-aggregate the raw data in your warehouse so that it's ready for analysis.

## InterSystems IRIS

[InterSystems IRIS](https://www.intersystems.com/data-platform/) is a data platform that provides advanced technologies for building and deploying data-intensive applications. It is a high-performance, multidimensional database that is optimized for complex data and real-time analytics. It is designed to support a wide range of data management, analysis, and integration tasks, and provides features such as a high-performance database engine, a powerful analytics engine, and support for building and deploying microservices. InterSystems IRIS is used by organizations in a variety of industries, including healthcare, finance, and government, to support their data-intensive applications and business processes.

### Start InterSystems IRIS Locally with Docker Compose

docker-compose.yml

```yml
version: '3'
services:
  iris:
    image: intersystemsdc/iris-community
    command:
      - -a
      # by default it starts with a requirement to change passwords for system users
      - iris session iris -U %SYS '##class(Security.Users).UnExpireUserPasswords("*")'
    ports:
      - 1972:1972
      - 52773:52773
```

Ports:

- 1972 - SuperPort - Binary protocol
- 52773 - Internal WebServer, internal System Management Portal is available by [http://localhost:52773/csp/sys/UtilHome.csp](http://localhost:52773/csp/sys/UtilHome.csp)

```shell
docker-compose up -d
```

_Default login and password `_SYSTEM` and `SYS`_

### Configure dbt

.dbt/profiles.yml

```yml
...
    iris:
      type: iris
      host: localhost
      port: 1972
      user: _SYSTEM
      pass: SYS
      namespace: USER
      schema: dbt
```

Required parameters:

- type = iris
- host | hostname | server
- port
- namespace | database
- user | username
- pass | password
- schema

Optional parameters:

- driver: which DB-API driver the adapter connects through. One of:
  - `iris` (default when available): `iris.dbapi` from `intersystems-irispython`,
    installed as a dependency. Works with `intersystems-iris` on top of it too.
  - `sqlalchemy`: connect through the `sqlalchemy-intersystems-iris` dialect
    (`pip install dbt-iris[sqlalchemy]`). Uses the dialect's connection hooks and pooling.
  - `vendored`: the `intersystems_iris` 3.x pure-Python driver bundled in older wheels,
    if you install it yourself; the wheel no longer bundles it. Kept for compatibility
    only. The driver rewrites most CTEs into subqueries, but IRIS refuses the ones it does not
    rewrite, such as a CTE with a column list (SQLCODE -385: protocol 65, where 69 is
    required) and `WITH RECURSIVE` (SQLCODE -400).

  The `DBT_IRIS_DRIVER` environment variable sets the same thing without editing the profile.

### IRIS SQL notes

- A `WITH` clause may not appear inside a derived table, and a `WITH` nested
  inside another CTE's body fails to compile on the server. The adapter
  rewrites both shapes automatically (hoisting and flattening CTEs), so
  ephemeral models and models with their own CTEs work as tests, views, and
  tables. Recursive CTEs are not yet supported by IRIS (DP-449898).
- Multi-row `INSERT ... VALUES (...), (...)` is not IRIS SQL. Seeds are loaded
  with `executemany`; write your own inserts as `INSERT ... SELECT ... UNION ALL`.
- Incremental strategy support: `append` today. `merge` waits on IRIS `MERGE`
  (DP-419256).

## Useful Links

- [InterSystems Documentation](https://docs.intersystems.com/)
- [InterSystems Developer Community](http://community.intersystems.com/)
