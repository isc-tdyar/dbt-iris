# dbt-iris release checklist

dbt Labs ended the Trusted Adapter Program for dbt v1. Adapters are now listed together on the
[community adapters](https://docs.getdbt.com/docs/community-adapters) page, and the
[adapter guide](https://docs.getdbt.com/guides/adapter-creation) sets out what a listed adapter
should provide. This checklist follows that guide (read 2026-10-24).

## Making the adapter available

| Item                                           | State for 2.0.0                                                                                       |
| ---------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Hosted on a public git provider                | [caretdev/dbt-iris](https://github.com/caretdev/dbt-iris)                                             |
| Published on PyPI                              | `dbt-iris`; 2.0.0 wheel and sdist build and pass `twine check` and `check-wheel-contents`; not published |
| Listed on the community adapters page          | Entry drafted in `docs/dbt-docs-site/community-adapters-entry.md`; needs a PR to dbt-labs/docs.getdbt.com |
| "Connect" page (`iris-setup.md`)               | Drafted in `docs/dbt-docs-site/iris-setup.md`, with every profile setting                             |
| "Configure" page (`iris-configs.md`)           | Drafted in `docs/dbt-docs-site/iris-configs.md`: materializations, strategies, capability checks, limits |
| Sidebar entry (`website/sidebars.js`)          | Part of the same docs PR                                                                               |
| README links to the docs-site pages            | Links to the drafts now; switch to the docs.getdbt.com URLs once the docs PR is merged               |
| `profile_template.yml` for `dbt init`          | Added                                                                                                 |

## Essential functionality

| Item                                | Covered by                                                                                          |
| ----------------------------------- | --------------------------------------------------------------------------------------------------- |
| Table, view and seed materializations | `tests/functional/adapter/test_basic.py` (dbt's `BaseSimpleMaterializations` and others), `test_views.py` |
| dbt tests                           | `BaseSingularTests`, `BaseGenericTests`, `BaseSingularTestsEphemeral`                                 |
| Incremental strategies              | `test_incremental.py`, `test_merge_strategy.py`, `test_microbatch.py`, `test_end_to_end_incremental.py` |
| Snapshots                           | `BaseSnapshotCheckCols`, `BaseSnapshotTimestamp`, `test_end_to_end_incremental.py`                    |
| Ephemeral models                    | `BaseEphemeral`, `test_recursive.py`                                                                  |

## Staying current with dbt

- CI runs on the two latest dbt-core minors (1.11 and 1.12) and Python 3.10 to 3.12.
- Patch releases contain fixes only.

## Security practices

| Practice                                           | State                                                                                       |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| No credentials or platform data in logs or files   | `_connection_keys` leaves out the password; the capability probes and lock retries log no data |
| No API calls beyond what dbt features need         | The only extra statements are the two capability probes (a `MERGE` into a table that does not exist, and a two-row `WITH RECURSIVE`) |
| No hidden code or behaviour                        | All adapter code is in this repository                                                      |

## Community

- Issues in this repository answered by the maintainer.
- Questions in dbt Community Slack, `#adapter-ecosystem`.
