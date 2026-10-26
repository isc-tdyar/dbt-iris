---
title: "InterSystems IRIS setup"
description: "Read this guide to learn about the InterSystems IRIS warehouse setup in dbt."
meta:
  maintained_by: Community
  authors: "CaretDev (Dmitry Maslennikov) and contributors"
  github_repo: "caretdev/dbt-iris"
  pypi_package: "dbt-iris"
  min_core_version: "v1.10.0"
  cloud_support: "Not Supported"
  min_supported_version: "IRIS 2026.1"
  slack_channel_name: "n/a"
  slack_channel_link: "https://getdbt.slack.com/archives/C030A0UF5LM"
  platform_name: "InterSystems IRIS"
  config_page: "/reference/resource-configs/iris-configs"
---

<!-- Draft for a pull request to dbt-labs/docs.getdbt.com at
     website/docs/docs/local/connect-data-platform/iris-setup.md -->

import SetUpPages from '/snippets/\_setup-pages-intro.md';

<SetUpPages meta={frontMatter.meta} />

## Installing dbt-iris

```shell
python -m pip install dbt-core dbt-iris
```

`pip install dbt-iris` also installs `intersystems-irispython`, the InterSystems DB-API driver
the adapter connects through. dbt-iris 2.0.0 needs dbt-core 1.10 or later, Python 3.10 or later
and InterSystems IRIS 2026.1 or later. It is tested on IRIS 2026.1, 2026.2 and 2026.3.

## Connecting to InterSystems IRIS

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

| Setting    | Required | Aliases          | Meaning                                                    |
| ---------- | -------- | ---------------- | ---------------------------------------------------------- |
| `type`     | yes      |                  | `iris`                                                     |
| `hostname` | yes      | `host`, `server` | Host name or address of the IRIS server                    |
| `port`     | yes      |                  | Superserver port, 1972 by default                          |
| `database` | yes      | `namespace`      | IRIS namespace, such as `USER` (not an IRIS database file) |
| `username` | yes      | `user`           | IRIS user                                                  |
| `password` | yes      | `pass`           | Password                                                   |
| `schema`   | yes      |                  | SQL schema dbt builds models in                            |
| `threads`  | no       |                  | Models built at once, 1 by default                         |

Check the connection with `dbt debug`.

Users need the SQL privileges to create tables and views in `schema`. Snapshots also need a
`HASH` SQL function, written in ObjectScript, that the adapter installs when it creates a schema.
IRIS refuses `CREATE FUNCTION` with code to a user who has only SQL privileges; the `%Developer`
role is enough. Without it, dbt warns and runs everything except snapshots.
