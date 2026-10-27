"""Refuse a GROUP BY that contains a column number.

IRIS reads a number in GROUP BY as a constant, not as a select-list position (its SQL reference
says so): GROUP BY 1 puts every row into one group, and next to named columns the number is
ignored, with no error either way. Every other warehouse dbt supports reads GROUP BY 1 as the
first column, and dbt_utils.group_by(n) writes it, so such SQL would return wrong aggregates.
ORDER BY 1 works on IRIS and is left alone.
"""
import re
from typing import List

from dbt_common.exceptions import DbtRuntimeError

from dbt.adapters.iris.union_types import _mask

_GROUP_BY = re.compile(r"\bgroup\s+by\b", re.IGNORECASE)
_CLAUSE_END = re.compile(
    r"\b(?:having|order\s+by|limit|union|except|intersect|offset|fetch|window)\b", re.IGNORECASE
)
_NUMBER = re.compile(r"\d+")


def numbers(sql: str) -> List[str]:
    """Every bare number used as a GROUP BY item in sql, in order."""
    masked = _mask(sql)
    depth, level = [], 0
    for c in masked:
        if c == "(":
            level += 1
        depth.append(level)
        if c == ")":
            level -= 1
    found: List[str] = []
    for m in _GROUP_BY.finditer(masked):
        clause_depth, start, i = depth[m.start()], m.end(), m.end()
        items = []
        while i < len(masked):
            d = depth[i]
            if d < clause_depth or (masked[i] == ")" and d == clause_depth):
                break
            if d == clause_depth:
                if masked[i] == ",":
                    items.append(masked[start:i])
                    start = i + 1
                elif _CLAUSE_END.match(masked, i) and (i == 0 or not masked[i - 1].isalnum()):
                    break
                elif masked[i] == ";":
                    break
            i += 1
        items.append(masked[start:i])
        found.extend(item.strip() for item in items if _NUMBER.fullmatch(item.strip()))
    return found


def check(sql: str) -> None:
    """Raise before sql runs if a GROUP BY in it contains a column number."""
    found = numbers(sql)
    if found:
        raise DbtRuntimeError(
            f"dbt-iris: GROUP BY {', '.join(found)}: IRIS reads a number in GROUP BY as a "
            "constant, not as a column position, so every row falls into one group (or, next to "
            "named columns, the number is ignored), and it raises no error. Name the columns or "
            "expressions in GROUP BY instead, for example group by status instead of group by 1."
        )
