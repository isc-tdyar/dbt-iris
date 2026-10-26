"""Refuse a table build whose UNION mixes a DATE or TIME with another type in one column.

When IRIS builds a table from such a UNION (CREATE TABLE AS, INSERT ... SELECT) it stores the
DATE or TIME values as their internal numbers: '66154' for 2022-02-14, '36672' for 10:11:12. A
plain SELECT of the same UNION looks right, so nothing else would catch it. Each branch's column
types are read with a zero-row query before the statement runs; the union as a whole reports
only VARCHAR.

Measured on IRIS 2026.1 to 2026.3: DATE with text, a number or TIME, and TIME with anything but
TIME, store wrong values; DATE with TIMESTAMP, and TIMESTAMP with text, are stored correctly. A
bare NULL reports as a one-character VARCHAR, so a branch that looks like one is not judged (a
real VARCHAR(1) column looks the same). POSIXTIME reports as TIMESTAMP and cannot be told apart.

Best effort: a branch IRIS cannot describe on its own skips the check for its UNION.
"""
import re
from typing import Callable, List, Optional, Sequence, Tuple

from dbt_common.exceptions import DbtRuntimeError

_DATE, _TIME, _TIMESTAMP = {9, 91}, {10, 92}, {11, 93}
_TYPE_NAMES = {
    9: "DATE", 91: "DATE", 10: "TIME", 92: "TIME", 11: "TIMESTAMP", 93: "TIMESTAMP",
    12: "VARCHAR", 1: "CHAR", -1: "LONGVARCHAR", -9: "VARCHAR", 4: "INTEGER", -5: "BIGINT",
    5: "SMALLINT", -6: "TINYINT", 2: "NUMERIC", 3: "DECIMAL", 8: "DOUBLE", 6: "FLOAT", -7: "BIT",
}  # fmt: skip

_TARGET = re.compile(
    r"^\s*(?:create\s+(?:global\s+temporary\s+)?table\s+\S+\s+as\b"
    r"|insert\s+into\s+\S+\s*(?:\([^)]*\))?(?=\s*(?:select|with|\()))",
    re.IGNORECASE,
)
_UNION = re.compile(r"\bunion(?:\s+all|\s+distinct)?\b", re.IGNORECASE)
_ORDER_BY = re.compile(r"\border\s+by\b", re.IGNORECASE)
_WITH = re.compile(r"\s*with(?:\s+recursive)?\b", re.IGNORECASE)
_AS = re.compile(r"\s*as\s*\(", re.IGNORECASE)
_NAME = re.compile(r'\s*(?:"[^"]*"|[\w%$]+)')

Description = Sequence[tuple]


def _mask(sql: str) -> str:
    """sql with string literals, quoted names and comments blanked out, same length."""
    out, i, n = list(sql), 0, len(sql)
    while i < n:
        if sql[i] in "'\"":
            quote, j = sql[i], i + 1
            while j < n and not (sql[j] == quote and not sql.startswith(quote * 2, j)):
                j += 2 if sql.startswith(quote * 2, j) else 1
            end = min(j + 1, n)
        elif sql.startswith("--", i):
            j = sql.find("\n", i)
            end = n if j < 0 else j
        elif sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            end = n if j < 0 else j + 2
        else:
            i += 1
            continue
        out[i:end] = " " * (end - i)
        i = end
    return "".join(out)


def _strip_comments(sql: str) -> str:
    """Leading comments removed, so the statement keyword is first."""
    masked = _mask(sql)
    i = 0
    while i < len(sql) and masked[i].isspace():
        i += 1
    return sql[i:]


def target_body(sql: str) -> Optional[str]:
    """The SELECT a CREATE TABLE AS or INSERT ... SELECT builds the table from, else None."""
    sql = _strip_comments(sql)
    m = _TARGET.match(_mask(sql))
    return sql[m.end() :] if m else None


def _pairs(masked: str) -> List[Tuple[int, int]]:
    """(open, close) index of every balanced parenthesis pair."""
    stack, pairs = [], []
    for i, c in enumerate(masked):
        if c == "(":
            stack.append(i)
        elif c == ")" and stack:
            pairs.append((stack.pop(), i))
    return pairs


def _leading_with(body: str, masked: str, close_of: dict) -> int:
    """Index just past a leading WITH list, or 0 when there is none."""
    m = _WITH.match(masked)
    if not m:
        return 0
    i = m.end()
    while True:
        name = _NAME.match(masked, i)
        if not name:
            return 0
        i = name.end()
        j = len(masked[i:]) - len(masked[i:].lstrip())
        if masked[i + j : i + j + 1] == "(":  # a column list
            i = close_of.get(i + j, i + j) + 1
        a = _AS.match(masked, i)
        if not a:
            return 0
        i = close_of.get(a.end() - 1, a.end() - 1) + 1
        k = len(masked[i:]) - len(masked[i:].lstrip())
        if masked[i + k : i + k + 1] != ",":
            return i
        i += k + 1


def union_groups(body: str) -> Tuple[str, List[List[str]]]:
    """(leading WITH prefix, branches of every UNION in body), outermost first."""
    masked = _mask(body)
    pairs = _pairs(masked)
    close_of = {o: c for o, c in pairs}
    prefix_end = _leading_with(body, masked, close_of)
    depth = [0] * (len(masked) + 1)
    for o, c in pairs:
        for k in range(o + 1, c):
            depth[k] += 1
    segments = [(prefix_end, len(body), 0)] + sorted((o + 1, c, depth[o] + 1) for o, c in pairs)
    groups = []
    for start, end, level in segments:
        cuts = [m for m in _UNION.finditer(masked, start, end) if depth[m.start()] == level]
        if not cuts:
            continue
        bounds = [start] + [x for m in cuts for x in (m.start(), m.end())] + [end]
        branches = [body[bounds[k] : bounds[k + 1]] for k in range(0, len(bounds), 2)]
        last_start = bounds[-2]
        order = [
            m for m in _ORDER_BY.finditer(masked, last_start, end) if depth[m.start()] == level
        ]
        if order:
            branches[-1] = body[last_start : order[0].start()]
        groups.append([b.strip() for b in branches])
    return body[:prefix_end].strip(), groups


def _looks_null(column: tuple) -> bool:
    return column[1] == 12 and column[4] == 1 and column[6] == 1


def _name(code: int) -> str:
    return _TYPE_NAMES.get(code, f"type {code}")


def mismatches(branches: Sequence[Description]) -> List[Tuple[str, List[str]]]:
    """(column name, type names) for each column the branches store wrongly together."""
    if len({len(b) for b in branches}) != 1:
        return []
    found = []
    for position in range(len(branches[0])):
        codes = {b[position][1] for b in branches if not _looks_null(b[position])}
        bad = (codes & _DATE and codes - _DATE - _TIMESTAMP) or (codes & _TIME and codes - _TIME)
        if bad:
            found.append((branches[0][position][0], sorted({_name(c) for c in codes})))
    return found


_STORED_AS = {
    "DATE": "the DATE values as internal day numbers (for example '66154' for 2022-02-14)",
    "TIME": "the TIME values as seconds since midnight (for example '36672' for 10:11:12)",
}


def message(found: List[Tuple[str, List[str]]]) -> str:
    lines = []
    for name, types in found:
        kind = "DATE" if "DATE" in types else "TIME"
        others = " or ".join(t for t in types if t != kind)
        lines.append(
            f"Column '{name}' is {kind} in one UNION branch and {others} in another. When IRIS "
            f"builds a table from this UNION it stores {_STORED_AS[kind]}, and raises no error."
        )
    return (
        "dbt-iris: " + " ".join(lines) + " Give the column the same type in every branch, for "
        "example cast('2022-02-15' as date) instead of '2022-02-15'."
    )


def check(sql: str, describe: Callable[[str], Optional[Description]]) -> None:
    """Raise before sql builds a table from a UNION that IRIS would store wrongly.

    describe(query) returns the cursor description for query, or None if it cannot run."""
    body = target_body(sql)
    if body is None or not _UNION.search(_mask(body)):
        return
    prefix, groups = union_groups(body)
    lead = f"{prefix} " if prefix else ""
    found = []
    for branches in groups:
        described = []
        for branch in branches:
            description = describe(f"{lead}select * from ({branch}) dbt_iris_branch where 1=0")
            if not description:
                break
            described.append(description)
        else:
            found.extend(mismatches(described))
    if found:
        raise DbtRuntimeError(message(found))
