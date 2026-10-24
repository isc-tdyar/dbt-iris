from typing import Optional, List, Tuple
import re
import agate
from dbt_common.exceptions import MacroArgTypeError
from dbt_common.exceptions import DbtRuntimeError
from dbt.adapters.base.relation import BaseRelation

from dbt.adapters.sql import SQLAdapter
from dbt.adapters.base.meta import available
from dbt.adapters.events.logging import AdapterLogger

from dbt.adapters.iris import IRISConnectionManager
from dbt.adapters.iris import IRISColumn
from dbt.adapters.iris import IRISRelation

LIST_SCHEMAS_MACRO_NAME = "list_schemas"
LIST_RELATIONS_MACRO_NAME = "list_relations_without_caching"

logger = AdapterLogger("iris")


class _SqlScanner:
    """Minimal scanner for the leading WITH clause of an IRIS SQL statement.
    Understands nested parentheses, single and double quoted strings, and
    comments. Nothing else: it exists to relocate CTEs, not to parse SQL."""

    def __init__(self, sql: str):
        self.sql = sql
        self.n = len(sql)

    def skip_ws(self, i: int) -> int:
        sql, n = self.sql, self.n
        while i < n:
            if sql[i].isspace():
                i += 1
            elif sql.startswith("--", i):
                j = sql.find("\n", i)
                i = n if j < 0 else j + 1
            elif sql.startswith("/*", i):
                j = sql.find("*/", i + 2)
                i = n if j < 0 else j + 2
            else:
                break
        return i

    def skip_balanced(self, i: int) -> int:
        """i points at '('; return index just past its matching ')'."""
        sql, n = self.sql, self.n
        depth = 0
        while i < n:
            c = sql[i]
            if c == "'":
                i += 1
                while i < n:
                    if sql[i] == "'":
                        if i + 1 < n and sql[i + 1] == "'":
                            i += 2
                            continue
                        break
                    i += 1
                i += 1
                continue
            if c == '"':
                j = sql.find('"', i + 1)
                i = n if j < 0 else j + 1
                continue
            if sql.startswith("--", i):
                j = sql.find("\n", i)
                i = n if j < 0 else j + 1
                continue
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    return i + 1
            i += 1
        return n

    def word_at(self, i: int, word: str) -> bool:
        sql, n = self.sql, self.n
        return sql[i : i + len(word)].lower() == word and (
            i + len(word) >= n or not (sql[i + len(word)].isalnum() or sql[i + len(word)] == "_")
        )

    def parse_leading_with(self):
        """Return (recursive, [(header, body)], body_start, body_text) or None.

        header is the CTE name plus any column list, e.g. 'tree(id, d)';
        body is the text inside the CTE's parentheses."""
        sql = self.sql
        i = self.skip_ws(0)
        if not self.word_at(i, "with"):
            return None
        i = self.skip_ws(i + 4)
        recursive = False
        if self.word_at(i, "recursive"):
            recursive = True
            i = self.skip_ws(i + 9)
        ctes = []
        while True:
            h0 = i
            if i < self.n and sql[i] == '"':
                j = sql.find('"', i + 1)
                i = self.n if j < 0 else j + 1
            else:
                while i < self.n and (sql[i].isalnum() or sql[i] in "_$"):
                    i += 1
            k = self.skip_ws(i)
            if k < self.n and sql[k] == "(":  # column list
                i = self.skip_balanced(k)
                k = self.skip_ws(i)
            header = sql[h0:i].strip()
            if not header or not self.word_at(k, "as"):
                return None
            k = self.skip_ws(k + 2)
            if k >= self.n or sql[k] != "(":
                return None
            close = self.skip_balanced(k)
            body = sql[k + 1 : close - 1]
            ctes.append((header, body))
            j = self.skip_ws(close)
            if j < self.n and sql[j] == ",":
                i = self.skip_ws(j + 1)
                continue
            return recursive, ctes, close, sql[close:]


def split_leading_ctes(sql: str) -> Tuple[str, str]:
    """Split ``WITH a AS (...), b AS (...) <body>`` into (cte_prefix, body).

    IRIS SQL rejects a WITH clause inside a derived table, and dbt wraps model
    SQL in ``select ... from ( <model sql> ) t`` for tests and column
    introspection. Callers hoist the prefix above the wrapper and place only
    the body inside it. Returns ("", sql) when there is no leading WITH.
    """
    parsed = _SqlScanner(sql).parse_leading_with()
    if parsed is None:
        return "", sql
    _, _, close, body = parsed
    return sql[:close], body


def flatten_nested_ctes(sql: str) -> str:
    """Hoist CTEs defined inside another CTE's body into the outer WITH list.

    dbt injects an ephemeral model as ``__dbt__cte__<name> AS ( <model sql> )``;
    when the model itself begins with WITH the result is a WITH nested inside a
    CTE body, which IRIS's SQL server fails to compile (SQLCODE -400,
    ``<UNDEFINED> %qinfo("type")`` at Compile^%SYS.SQLSRV). Inner CTEs are
    placed before the CTE that referenced them, preserving order. SQL without
    a leading WITH, or without nesting, is returned unchanged.
    """
    parsed = _SqlScanner(sql).parse_leading_with()
    if parsed is None:
        return sql
    recursive, ctes, _, body = parsed

    def expand(header, cte_body):
        inner = _SqlScanner(cte_body).parse_leading_with()
        if inner is None:
            return [(header, cte_body)]
        _, inner_ctes, _, inner_body = inner
        out = []
        for h, b in inner_ctes:
            out.extend(expand(h, b))
        out.append((header, inner_body.strip()))
        return out

    flat = []
    changed = False
    for header, cte_body in ctes:
        expanded = expand(header, cte_body)
        if len(expanded) != 1 or expanded[0][1] is not cte_body:
            changed = True
        flat.extend(expanded)
    if not changed:
        return sql
    head = "with recursive " if recursive else "with "
    return head + ",\n".join(f"{h} as ({b})" for h, b in flat) + "\n" + body.lstrip("\n")


class IRISAdapter(SQLAdapter):
    """
    Controls actual implmentation of adapter, and ability to override certain methods.
    """

    Relation = IRISRelation
    Column = IRISColumn
    ConnectionManager = IRISConnectionManager

    @available
    def flatten_nested_ctes(self, sql: str):
        """For CREATE VIEW / CREATE TABLE AS: IRIS accepts a leading WITH but
        not a WITH nested inside a CTE body (ephemeral model with its own CTEs)."""
        return flatten_nested_ctes(sql)

    @available
    def split_leading_ctes(self, sql: str):
        """For macros that wrap model SQL in a derived table: flatten any nested
        CTEs, then return (cte_prefix, body) so the prefix can be hoisted."""
        return split_leading_ctes(flatten_nested_ctes(sql))

    def run_sql_for_tests(self, sql, fetch, conn):
        # intersystems-irispython 5.x DataRow objects are proxies onto the cursor;
        # dbt's test utilities read them after this method returns. Copy them out.
        cursor = conn.handle.cursor()
        try:
            cursor.execute(sql)
            if hasattr(conn.handle, "commit"):
                conn.handle.commit()
            if fetch == "one":
                row = cursor.fetchone()
                return None if row is None else tuple(row)
            elif fetch == "all":
                return [tuple(r) for r in cursor.fetchall()]
            else:
                return
        except BaseException as e:
            if conn.handle and not getattr(conn.handle, "closed", True):
                conn.handle.rollback()
            print(sql)
            print(e)
            raise
        finally:
            conn.transaction_open = False

    @classmethod
    def date_function(cls):
        """
        Returns canonical date func
        """
        return "datenow()"

    @classmethod
    def convert_text_type(cls, agate_table, col_idx):
        min_length = 65535
        column = agate_table.columns[col_idx]
        lengths = [len(d.encode("utf-8")) for d in column.values_without_nulls()]
        max_len = max(lengths) if lengths else min_length
        length = max_len if max_len > min_length else min_length
        return "varchar({})".format(length)

    @classmethod
    def convert_boolean_type(cls, agate_table: agate.Table, col_idx: int) -> str:
        return "bit"

    @classmethod
    def convert_number_type(cls, agate_table, col_idx):
        decimals = agate_table.aggregate(agate.MaxPrecision(col_idx))
        return "float" if decimals else "integer"

    @classmethod
    def convert_datetime_type(cls, agate_table: agate.Table, col_idx: int) -> str:
        return "datetime"

    def timestamp_add_sql(self, add_to: str, number: int = 1, interval: str = "hour") -> str:
        return f"dateadd('{interval}', {number}, {add_to})"

    def create_schema(self, schema_relation: BaseRelation) -> None:
        self.execute_macro("create_function_hash", kwargs={})

    def drop_schema(self, schema_relation) -> None:
        try:
            relations = self.list_relations_without_caching(schema_relation)
            for relation in relations:
                self.drop_relation(relation)
            self.commit_if_has_connection()
            self.cache.drop_schema(schema_relation.database, schema_relation.schema)
        except Exception:
            raise

    def check_schema_exists(self, database, schema):
        results = self.execute_macro(LIST_SCHEMAS_MACRO_NAME, kwargs={"database": database})

        exists = True if schema in [row[0] for row in results] else False
        return exists

    def list_relations_without_caching(self, schema_relation: IRISRelation) -> List[IRISRelation]:
        kwargs = {"schema_relation": schema_relation}
        try:
            results = self.execute_macro(LIST_RELATIONS_MACRO_NAME, kwargs=kwargs)
        except DbtRuntimeError as e:
            errmsg = getattr(e, "msg", "")
            if f"IRIS schema '{schema_relation}' not found" not in errmsg:
                description = "Error while retrieving information about"
                logger.debug(f"{description} {schema_relation}: {e.msg}")
            return []

        relations = []
        _database = schema_relation.database
        for row in results:
            if len(row) != 4:
                raise DbtRuntimeError(
                    "Invalid value from "
                    f'"iris__list_relations_without_caching({kwargs})", '
                    f"got {len(row)} values, expected 4"
                )
            _, name, _schema, relation_type = row
            relation = self.Relation.create(
                database=_database, schema=_schema, identifier=name, type=relation_type
            )
            relations.append(relation)
        return relations

    def get_rows_different_sql(
        self,
        relation_a: BaseRelation,
        relation_b: BaseRelation,
        column_names: Optional[List[str]] = None,
        except_operator: str = "EXCEPT",
    ) -> str:
        # TODO: IRIS does not support WITH and EXCEPT, no idea how to implement it, yet
        return "SELECT 0,0"

    def get_missing_columns(
        self, from_relation: IRISRelation, to_relation: IRISRelation
    ) -> List[IRISColumn]:
        """Returns a list of Columns in from_relation that are missing from
        to_relation.
        """
        if not isinstance(from_relation, self.Relation):
            raise MacroArgTypeError(
                method_name="get_missing_columns",
                arg_name="from_relation",
                got_value=from_relation,
                expected_type=self.Relation,
            )

        if not isinstance(to_relation, self.Relation):
            raise MacroArgTypeError(
                method_name="get_missing_columns",
                arg_name="to_relation",
                got_value=to_relation,
                expected_type=self.Relation,
            )

        from_columns = {
            col.name.lower(): col for col in self.get_columns_in_relation(from_relation)
        }

        to_columns = {col.name.lower(): col for col in self.get_columns_in_relation(to_relation)}

        missing_columns = set(from_columns.keys()) - set(to_columns.keys())

        return [
            col for (col_name, col) in from_columns.items() if col_name.lower() in missing_columns
        ]

    def submit_python_job(self, parsed_model: dict, compiled_code: str):
        schema = parsed_model["schema"]
        identifier = parsed_model["alias"]

        # IRIS Has issues with Python's comments
        compiled_code = re.sub(r"^[\s\t]*#.*$", "", compiled_code, flags=re.M)

        proc_name = f'"{schema}"."{identifier}__dbt_sp"'
        create_procedure = f"""
CREATE OR REPLACE PROCEDURE {proc_name} ()
RETURNS VARCHAR(10)
LANGUAGE PYTHON
{{
{compiled_code}
}}
"""

        response, _ = self.execute(create_procedure, auto_begin=False, fetch=False)
        response, _ = self.execute(f"SELECT {proc_name}()", auto_begin=False, fetch=True)
        self.execute(f"drop procedure if exists {proc_name}", auto_begin=False, fetch=False)
        return response

    def valid_incremental_strategies(self) -> List[str]:
        return ["append", "merge", "delete+insert"]

    def drop_relation(self, relation: BaseRelation):
        # if relation.type == "table":
        #     print("!!!! Dropping table with temporary property", relation)
        #     tmp_prop = "__dbt_tmp"
        #     try:
        #         self.execute(
        #             f'alter table {relation} add "{tmp_prop}" bit calculated',
        #             auto_begin=False,
        #             fetch=False,
        #         )
        #     except Exception as ex:
        #         print(
        #             "!!!! Failed to add temporary property, continuing anyway",
        #             relation,
        #             ex,
        #         )

        super().drop_relation(relation)
