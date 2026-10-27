from typing import Optional, List, Tuple
import base64
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
from dbt.adapters.iris import capabilities
from dbt.adapters.iris import materialized_view
from dbt.adapters.iris import union_types
from dbt.adapters.iris import connections
from dbt.adapters.iris.connections import _server_key

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


_STRING_TYPES = {
    "varchar",
    "char",
    "character",
    "character varying",
    "nvarchar",
    "nchar",
    "string",
}
_STREAM_TYPES = {"longvarchar", "longvarbinary", "text", "ntext", "clob", "blob", "image"}
_TEMPORAL_TYPES = {"date", "time", "timestamp", "datetime", "smalldatetime", "posixtime"}
_MAX_STRING = 3641144  # IRIS's longest string; a stream is compared on this many characters


def _comparable(quoted: str, dtype: str) -> str:
    """A column expression whose value EXCEPT compares the way other databases do."""
    if dtype in _STREAM_TYPES:
        return f"%EXACT(SUBSTRING({quoted}, 1, {_MAX_STRING}))"
    if dtype in _STRING_TYPES:
        return f"%EXACT({quoted})"
    if dtype in _TEMPORAL_TYPES:
        return f"%EXACT(CAST({quoted} AS VARCHAR(64)))"
    return quoted


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


_WITH_KW = re.compile(r"with(?:\s+recursive)?\b", re.IGNORECASE)
_RECURSIVE_KW = re.compile(r"with\s+recursive\b", re.IGNORECASE)
_CTE_NAME = re.compile(r'\s*("[^"]*"|[\w%$]+)')
_CTE_AS = re.compile(r"\s*as\s*\(", re.IGNORECASE)


def _skip_space(text: str, i: int) -> int:
    while i < len(text) and text[i].isspace():
        i += 1
    return i


def _with_list(sql: str, masked: str, close_of: dict, start: int):
    """Parse the WITH list starting at start: (recursive, [(cte start, cte end, name, body
    open)], end), or None when the text there is not a WITH list."""
    m = _WITH_KW.match(masked, start)
    if not m:
        return None
    recursive = bool(_RECURSIVE_KW.match(masked, start))
    i, ctes = m.end(), []
    while True:
        name = _CTE_NAME.match(sql, i)
        if not name:
            return None
        cte_start, i = name.start(1), name.end()
        j = _skip_space(masked, i)
        if masked.startswith("(", j):  # a column list
            i = close_of.get(j, j) + 1
        as_paren = _CTE_AS.match(masked, i)
        if not as_paren:
            return None
        end = close_of.get(as_paren.end() - 1)
        if end is None:
            return None
        ctes.append((cte_start, end + 1, name.group(1).strip('"').lower(), as_paren.end() - 1))
        i = _skip_space(masked, end + 1)
        if not masked.startswith(",", i):
            return recursive, ctes, end + 1
        i += 1


def _hoist_subquery_ctes(sql: str) -> str:
    """Lift a WITH out of a subquery (derived table, IN, UNION branch, scalar subquery) into the
    statement's top-level WITH, which IRIS accepts. A subquery whose CTE names are already in use
    is left alone: renaming would mean rewriting its references."""
    for _ in range(100):
        masked = union_types._mask(sql)
        close_of = dict(union_types._pairs(masked))
        lead = _skip_space(masked, 0)
        top = _with_list(sql, masked, close_of, lead)
        top_ctes = top[1] if top else []
        top_names = {cte[2] for cte in top_ctes}
        top_bodies = {cte[3] for cte in top_ctes}  # nested CTE bodies: flatten_nested_ctes
        candidates = [
            (o, c) for o, c in close_of.items()
            if o not in top_bodies and _WITH_KW.match(masked, _skip_space(masked, o + 1))
        ]  # fmt: skip
        innermost = [
            (o, c) for o, c in candidates
            if not any(o < o2 and c2 < c for o2, c2 in candidates)
        ]  # fmt: skip
        changed = False
        for o, c in sorted(innermost, reverse=True):
            inner = _with_list(sql, masked, close_of, _skip_space(masked, o + 1))
            if not inner or inner[2] > c:
                continue
            inner_recursive, inner_ctes, inner_end = inner
            if {cte[2] for cte in inner_ctes} & top_names:
                continue
            ctes_text = ", ".join(sql[cte[0] : cte[1]].strip() for cte in inner_ctes)
            out = sql[: o + 1] + sql[inner_end:c].strip() + sql[c:]
            owner = next((cte[0] for cte in top_ctes if cte[0] <= o < cte[1]), None)
            if owner is not None:
                out = out[:owner] + ctes_text + ", " + out[owner:]
            elif top:
                out = out[: top[2]] + ", " + ctes_text + out[top[2] :]
            else:
                out = out[:lead] + "with " + ctes_text + " " + out[lead:]
            if inner_recursive and not (top and top[0]):
                out = re.sub(r"^(\s*)with\b", r"\1with recursive", out, count=1, flags=re.I)
            sql, changed = out, True
            break
        if not changed:
            return sql
    return sql


def flatten_nested_ctes(sql: str) -> str:
    """Hoist CTEs defined inside another CTE's body into the outer WITH list.

    dbt injects an ephemeral model as ``__dbt__cte__<name> AS ( <model sql> )``;
    when the model itself begins with WITH the result is a WITH nested inside a
    CTE body, which IRIS's SQL server fails to compile (SQLCODE -400,
    ``<UNDEFINED> %qinfo("type")`` at Compile^%SYS.SQLSRV). Inner CTEs are
    placed before the CTE that referenced them, preserving order. SQL without
    a leading WITH, or without nesting, is returned unchanged.
    """
    sql = _hoist_subquery_ctes(sql)
    parsed = _SqlScanner(sql).parse_leading_with()
    if parsed is None:
        return sql
    recursive, ctes, _, body = parsed

    inner_recursive = []

    def expand(header, cte_body):
        inner = _SqlScanner(cte_body).parse_leading_with()
        if inner is None:
            return [(header, cte_body)]
        is_recursive, inner_ctes, _, inner_body = inner
        if is_recursive:
            inner_recursive.append(header)
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
    # A recursive CTE hoisted out of an ephemeral model keeps its parent WITH recursive.
    head = "with recursive " if (recursive or inner_recursive) else "with "
    return head + ",\n".join(f"{h} as ({b})" for h, b in flat) + "\n" + body.lstrip("\n")


def python_procedure_body(code: str, name: str) -> str:
    """The body of the stored procedure that runs a Python model inside IRIS.

    IRIS re-indents every line of a LANGUAGE PYTHON body, which changes multi-line strings, and
    has trouble with comment lines. The model's code is therefore sent as one base64 line and run
    with exec, so no line of it reaches IRIS's compiler.
    """
    encoded = base64.b64encode(code.encode("utf-8")).decode("ascii")
    return (
        "import base64\n"
        f'exec(compile(base64.b64decode("{encoded}").decode("utf-8"), "{name}", "exec"), '
        '{"__name__": "__dbt_python_model__"})\n'
        'return "OK"'
    )


# Strings, quoted identifiers, comments and statement separators, so a ";" inside any of the
# first four does not split.
_STATEMENT_TOKENS = re.compile(
    r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|--[^\n]*|/\*.*?\*/|;", re.DOTALL
)


def split_statements(sql: str) -> List[str]:
    """Split a script into statements; IRIS runs one statement per call."""
    pieces, start = [], 0
    for m in _STATEMENT_TOKENS.finditer(sql):
        if m.group() == ";":
            pieces.append(sql[start : m.start()])
            start = m.end()
    pieces.append(sql[start:])
    return [p.strip() for p in pieces if p.strip()]


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

    @available
    def purge_cached_queries(self, relation) -> None:
        """Drop the cached queries on relation after its columns changed, from a second connection.

        On IRIS 2026.3 and later, for a user with %All, a statement another connection had run on
        the table fails with "Invalid number of parameters" when it runs again on a new connection
        after ALTER TABLE ... ADD COLUMN. PURGE CACHED QUERIES BY TABLE clears it, but only when it
        comes from a connection other than the one that ran the ALTER. Best effort: a failure here
        is logged and never fails the run.
        """
        sql = f"purge cached queries by table {relation}"
        try:
            handle = connections.connect(self.connections.get_thread_connection().credentials)
        except Exception as e:
            logger.debug(f"{sql}: could not connect: {e}")
            return
        try:
            cursor = handle.cursor()
            cursor.execute(sql)
            cursor.close()
        except Exception as e:
            logger.debug(f"{sql}: {e}")
        finally:
            try:
                handle.close()
            except Exception:
                pass

    @available
    def materialized_view_mode(self, value) -> str:
        """'table' or 'view' for iris_materialized_view_as; anything else is a compile error."""
        return materialized_view.resolve_mode(value)

    @available
    def materialized_view_warning(self, invocation_id, nodes, selected) -> str:
        """The warning listing materialized_view models on the table default, once per run."""
        names = materialized_view.models_on_default(nodes, selected)
        if names and materialized_view.first_time(invocation_id):
            return materialized_view.warning_text(names)
        return ""

    def run_sql_for_tests(self, sql, fetch, conn):
        # intersystems-irispython 5.x DataRow objects are proxies onto the cursor;
        # dbt's test utilities read them after this method returns. Copy them out.
        cursor = conn.handle.cursor()
        try:
            for statement in split_statements(sql):
                cursor.execute(statement)
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
        """IRIS creates a schema with its first table; this installs HASH() for snapshots. IRIS
        refuses CREATE FUNCTION with ObjectScript code (SQLCODE -99) to a user without
        %Developer. Only snapshots use HASH, so that refusal is a warning, not a failed run."""
        try:
            self.execute_macro("create_function_hash", kwargs={})
        except DbtRuntimeError as e:
            if capabilities.sqlcode(e) != -99:
                raise
            logger.warning(
                "dbt-iris: could not install the HASH() SQL function that snapshots use: this "
                "IRIS user may not create functions with ObjectScript code. SQL models, seeds "
                "and tests run; snapshots and Python models need a user with the %Developer "
                "role (for snapshots, HASH() installed once by such a user is enough)."
            )

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
        """Row-count difference and number of rows in one relation but not the other, both
        directions, as dbt's test helper check_relations_equal expects.

        A bare comparison on IRIS treats strings under SQLUPPER (case and trailing spaces
        ignored), never matches a stream column, and compares a DATE with a VARCHAR by the
        DATE's internal value. So each column is normalised by its own type on each side:
        strings exact, streams by content, dates and times as their ODBC text.

        The rows on one side only are counted with UNION ALL and GROUP BY, not EXCEPT: on IRIS
        2026.1 to 2026.3, EXCEPT (and NOT EXISTS) over a view that groups by an %EXACT-collated
        column fails with SQLCODE -400 <UNDEFINED>. A group that only one side contributes to is
        a distinct row in one relation and not the other, which is what EXCEPT counted.
        except_operator is accepted for dbt's signature and not used."""
        columns_a = self.get_columns_in_relation(relation_a)
        columns_b = self.get_columns_in_relation(relation_b)
        names = column_names or [c.name for c in columns_a]

        def expressions(columns) -> List[str]:
            types = {c.name.lower(): (c.dtype or "").lower() for c in columns}
            return [_comparable(self.quote(n), types.get(n.lower(), "")) for n in names]

        a, b = relation_a, relation_b
        aliases = [f"dbt_iris_c{i}" for i in range(1, len(names) + 1)]
        side_a = ", ".join(f"{e} as {alias}" for e, alias in zip(expressions(columns_a), aliases))
        side_b = ", ".join(expressions(columns_b))
        return (
            f"select (select count(*) from {a}) - (select count(*) from {b}), "
            f"(select count(*) from (select {', '.join(aliases)} from ("
            f"select {side_a}, 1 as dbt_iris_side from {a} "
            f"union all select {side_b}, 2 from {b}"
            f") z group by {', '.join(aliases)} having min(dbt_iris_side) = max(dbt_iris_side)) x)"
        )

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

        proc_name = f'"{schema}"."{identifier}__dbt_sp"'
        create_procedure = f"""
CREATE OR REPLACE PROCEDURE {proc_name} ()
RETURNS VARCHAR(10)
LANGUAGE PYTHON
{{
{python_procedure_body(compiled_code, f"{schema}.{identifier}")}
}}
"""

        response, _ = self.execute(create_procedure, auto_begin=False, fetch=False)
        response, _ = self.execute(f"SELECT {proc_name}()", auto_begin=False, fetch=True)
        self.execute(f"drop procedure if exists {proc_name}", auto_begin=False, fetch=False)
        return response

    def valid_incremental_strategies(self) -> List[str]:
        return ["append", "merge", "delete+insert", "microbatch"]

    @available
    def supports_merge(self) -> bool:
        """Whether the connected server accepts MERGE INTO (asked once per server)."""
        connection = self.connections.get_thread_connection()
        return capabilities.supports(_server_key(connection), connection.handle, "merge")

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
