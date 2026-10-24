"""What the connected IRIS server accepts, asked once per server and cached.

Two capabilities change what the adapter does:

- ``merge``: whether the server accepts ``MERGE INTO``. The merge strategy uses it when present
  and an UPDATE plus INSERT otherwise.
- ``recursive_cte``: whether the server accepts ``WITH RECURSIVE``. A statement that uses it on
  a server that does not is refused before it runs, with a message naming the capability.

The probes have no side effects: the MERGE probe targets a table that does not exist, so a
server that understands MERGE answers "table not found" and one that does not answers with a
syntax error.
"""
import re
import threading
from typing import Callable, Dict, Optional, Tuple

from dbt_common.exceptions import DbtRuntimeError

_PROBE_TABLE = "DBT_IRIS_CAPABILITY_PROBE_NO_SUCH_TABLE"
MERGE_PROBE = (
    f"MERGE INTO {_PROBE_TABLE} t USING (SELECT 1 AS id) s ON t.id = s.id "
    "WHEN NOT MATCHED THEN INSERT (id) VALUES (s.id)"
)
RECURSIVE_PROBE = (
    "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r WHERE n < 2) SELECT n FROM r"
)

# SQLCODEs that mean the server did not understand the statement at all
_SYNTAX_SQLCODES = {-1, -25, -51}
_SQLCODE = re.compile(r"SQLCODE:\s*<(-?\d+)>")
_RECURSIVE = re.compile(r"\bwith\s+recursive\b", re.IGNORECASE)
# String literals, -- line comments and /* block */ comments, in one pass so that a comment
# marker inside a string (or a quote inside a comment) is read correctly.
_LITERALS_AND_COMMENTS = re.compile(r"'(?:[^']|'')*'|--[^\n]*|/\*.*?\*/", re.DOTALL)

RECURSIVE_REFUSED = (
    "This IRIS server{version} does not accept WITH RECURSIVE (recursive common table "
    "expressions), and this model uses one. Rewrite the model without recursion (see "
    '"Recursive CTEs" in the dbt-iris docs for a pattern), or run it on an IRIS release that '
    "supports recursive CTEs."
)
_ZVERSION = re.compile(r"\)\s+(\d{4}\.\d[\w.]*\s+\(Build\s+\w+\))")


def sqlcode(exc: BaseException) -> Optional[int]:
    m = _SQLCODE.search(str(exc))
    return int(m.group(1)) if m else None


def _run(handle, sql: str, fetch: bool) -> None:
    cursor = handle.cursor()
    try:
        cursor.execute(sql)
        if fetch:
            cursor.fetchall()
    finally:
        try:
            cursor.close()
        except Exception:
            pass


# A probe error without an SQLCODE (connection lost, timeout) says nothing about the server, so
# the probes raise it instead of answering, and supports() does not cache it.


def probe_merge(handle) -> bool:
    try:
        _run(handle, MERGE_PROBE, fetch=False)
    except Exception as e:
        code = sqlcode(e)
        if code is None:
            raise
        return code not in _SYNTAX_SQLCODES
    return True


def probe_recursive_cte(handle) -> bool:
    try:
        _run(handle, RECURSIVE_PROBE, fetch=True)
    except Exception as e:
        if sqlcode(e) is None:
            raise
        return False
    return True


PROBES: Dict[str, Callable] = {"merge": probe_merge, "recursive_cte": probe_recursive_cte}

ServerKey = Tuple[str, int, str]
_cache: Dict[ServerKey, Dict[str, bool]] = {}
_lock = threading.Lock()


def clear_cache() -> None:
    with _lock:
        _cache.clear()
        _versions.clear()


def supports(key: ServerKey, handle, name: str) -> bool:
    probe = PROBES[name]
    with _lock:
        known = _cache.get(key, {})
        if name in known:
            return known[name]
    result = probe(handle)
    with _lock:
        _cache.setdefault(key, {})[name] = result
    return result


def parse_zversion(zversion: str) -> Optional[str]:
    """'IRIS for UNIX (...) 2026.2 (Build 221U) Fri ...' -> '2026.2 (Build 221U)'."""
    m = _ZVERSION.search(zversion or "")
    return m.group(1) if m else None


_versions: Dict[ServerKey, str] = {}


def server_version(key: ServerKey, handle) -> Optional[str]:
    """The server's version for messages, read once per server; None if it cannot be read."""
    with _lock:
        if key in _versions:
            return _versions[key]
    try:
        cursor = handle.cursor()
        try:
            cursor.execute("SELECT $ZVERSION")
            version = parse_zversion(cursor.fetchone()[0])
        finally:
            cursor.close()
    except Exception:
        return None
    if version is not None:
        with _lock:
            _versions[key] = version
    return version


def uses_recursive_cte(sql: str) -> bool:
    return bool(_RECURSIVE.search(_LITERALS_AND_COMMENTS.sub(" ", sql)))


def check_statement(
    sql: str, ask: Callable[[str], bool], describe: Optional[Callable[[], Optional[str]]] = None
) -> None:
    """Refuse a statement the server cannot run, before sending it."""
    if uses_recursive_cte(sql) and not ask("recursive_cte"):
        version = describe() if describe else None
        raise DbtRuntimeError(
            RECURSIVE_REFUSED.format(version=f" (IRIS {version})" if version else "")
        )
