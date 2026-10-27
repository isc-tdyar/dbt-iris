# Contributing

This page is for people changing dbt-iris itself: how the repository is laid out, how to run the
tests against IRIS in Docker, and what CI checks.

## Layout

| Path                                    | What it holds                                                                     |
| --------------------------------------- | --------------------------------------------------------------------------------- |
| `dbt/adapters/iris/`                    | The Python side: connection, credentials, the adapter class and its SQL helpers   |
| `dbt/include/iris/macros/`              | The IRIS versions of dbt's macros: materializations, strategies, snapshots, seeds |
| `dbt/include/iris/profile_template.yml` | What `dbt init` asks for                                                          |
| `tests/unit/`                           | Tests that need no IRIS: SQL rewriting, settings, the docs and the CI workflow    |
| `tests/functional/`                     | dbt-tests-adapter suites and dbt-iris's own tests, run against a real IRIS        |
| `examples/jaffle_shop/`                 | The tutorial's project; CI builds it                                              |
| `docs/`                                 | This guide; `docs/dbt-docs-site/` holds the drafts for docs.getdbt.com            |

## Set up

```shell
python -m venv .venv && . .venv/bin/activate
python -m pip install -e . -r requirements-dev.txt
pre-commit install
```

`pre-commit` runs black, flake8 and mypy on every commit.

## Run the tests

Unit tests need nothing else:

```shell
python -m pytest tests/unit
```

Functional tests need an IRIS. Start the one in `docker-compose.yml`, then point the tests at it
with environment variables (these are the defaults):

```shell
docker compose up -d
export DBT_IRIS_HOST=localhost DBT_IRIS_PORT=1972 DBT_IRIS_USER=_SYSTEM DBT_IRIS_PASS=SYS
python -m pytest tests/functional
```

A full run takes about two and a half minutes. Two groups of tests are off unless you ask for
them:

| Variable                   | Turns on                                                                                                                               |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `DBT_IRIS_PYTHON_MODELS=1` | The Python model tests. IRIS's Python needs `pandas`, `sqlalchemy` and `sqlalchemy-iris`, as the repository's Dockerfile installs them |
| `DBT_IRIS_OVERLAP_TEST=1`  | The overlapping-runs test. It can leave the IRIS catalog damaged, so run it on a throwaway server                                      |

Run the tests one IRIS at a time. IRIS Community allows a small number of connections, and two
suites against one server can run out of them.

## Tests that are expected to fail

One test is marked as a strict expected failure because of an IRIS defect:
`TestUnionOfDateAndText` (a table built from a `DATE` and text `UNION` stores day numbers). When
an IRIS build fixes it, the test fails with "XPASS(strict)" and its reason says what to change.
Do not add `xfail` markers for adapter behaviour; fix the adapter or the test.

## What CI runs

`.github/workflows/main.yml`:

- unit tests and the pre-commit checks;
- the functional suites against IRIS Community 2026.2 (`latest-cd`) and 2026.3 (`latest-preview`)
  on Python 3.10, 3.11 and 3.12 with dbt-core 1.11 and 1.12, and against 2026.1 (`latest-em`) on
  Python 3.12 with dbt-core 1.12;
- the Python model tests;
- `dbt build` on `examples/jaffle_shop`, twice.

## Releasing

[`release-checklist.md`](release-checklist.md) lists what a release needs and the release-day
steps.
