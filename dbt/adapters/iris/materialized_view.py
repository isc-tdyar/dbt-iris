"""IRIS has no materialized views. A materialized_view model is built as a table (the default,
rebuilt on every run) or as a view, chosen with the iris_materialized_view_as config."""
import threading

from dbt_common.exceptions import CompilationError

SETTING = "iris_materialized_view_as"
MODES = ("table", "view")

_seen: set = set()
_lock = threading.Lock()


def resolve_mode(value) -> str:
    if value is None:
        return "table"
    mode = value.strip().lower() if isinstance(value, str) else value
    if mode not in MODES:
        allowed = ", ".join(f"'{m}'" for m in MODES)
        raise CompilationError(f"{SETTING} must be one of {allowed}, got {value!r}")
    return mode


def models_on_default(nodes, selected) -> list:
    """Names of the materialized_view models (among `selected`, or all) with no setting."""
    ids = nodes.keys() if selected is None else [i for i in selected if i in nodes]
    names = []
    for uid in ids:
        config = nodes[uid].get("config") or {}
        if config.get("materialized") == "materialized_view" and config.get(SETTING) is None:
            names.append(nodes[uid]["name"])
    return sorted(names)


def warning_text(names) -> str:
    return (
        "dbt-iris: IRIS has no materialized views. These materialized_view models are built as "
        f"tables and rebuilt on every dbt run: {', '.join(names)}. For a large model use "
        f"materialized='incremental', or set {SETTING}: view to build it as a view. "
        f"Set {SETTING}: table to keep tables without this warning."
    )


def first_time(key) -> bool:
    with _lock:
        if key in _seen:
            return False
        _seen.add(key)
        return True
