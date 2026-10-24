import os
import time
import importlib
from typing import Optional, Tuple, Any, Type, Union
from contextlib import contextmanager
from dataclasses import dataclass
from dbt.exceptions import DbtRuntimeError
from dbt.adapters.exceptions import FailedToConnectError
from dbt.adapters.contracts.connection import Credentials
from dbt.adapters.contracts.connection import Connection, AdapterResponse
from dbt.adapters.events.logging import AdapterLogger
from dbt.adapters.sql import SQLConnectionManager
from dbt_common.events.functions import fire_event
from dbt.adapters.events.types import ConnectionUsed, SQLQuery, SQLQueryStatus
from dbt_common.helper_types import Port
from mashumaro.jsonschema.annotations import Maximum, Minimum
from typing_extensions import Annotated

logger = AdapterLogger("iris")

# dbt-iris 2.0.0 connects only through `iris.dbapi` from intersystems-irispython.
# The bundled 3.x driver and the `driver` choice were removed. `driver: iris` (in the
# profile or DBT_IRIS_DRIVER) is still accepted so existing profiles keep working.
DRIVER_ENV = "DBT_IRIS_DRIVER"
_REMOVED = (
    "dbt-iris: the {source} {value!r} was removed in dbt-iris 2.0.0. The adapter now connects "
    "only through intersystems-irispython (iris.dbapi); remove the setting or set it to 'iris'."
)


def check_driver(credentials) -> None:
    for source, value in (
        ("profile setting driver =", getattr(credentials, "driver", None)),
        (f"environment variable {DRIVER_ENV} =", os.environ.get(DRIVER_ENV)),
    ):
        if value is None or value == "iris":
            continue
        raise FailedToConnectError(_REMOVED.format(source=source, value=value))
    if getattr(credentials, "driver", None) == "iris":
        logger.debug("dbt-iris: the `driver` profile setting is no longer needed")


def _dbapi():
    return importlib.import_module("iris.dbapi")


@dataclass
class IRISCredentials(Credentials):
    hostname: str
    username: str
    password: str
    port: Annotated[Port, Minimum(0), Maximum(65535)]
    application_name: Optional[str] = "dbt"
    driver: Optional[str] = None  # accepted only as "iris"; see check_driver

    _ALIASES = {
        "namespace": "database",
        "host": "hostname",
        "server": "hostname",
        "pass": "password",
        "user": "username",
    }

    @property
    def type(self) -> str:
        """Return name of adapter."""
        return "iris"

    @property
    def unique_field(self):
        """
        Hashed and included in anonymous telemetry to track adapter adoption.
        Pick a field that can uniquely identify one team/organization building with this adapter
        """
        return self.hostname

    def _connection_keys(self):
        """
        List of keys to display in the `dbt debug` output.
        """
        return (
            "hostname",
            "port",
            "database",
            "username",
            "schema",
            "application_name",
        )


class IRISConnectionManager(SQLConnectionManager):
    TYPE = "iris"

    @contextmanager
    def exception_handler(self, sql: str):
        """
        Returns a context manager, that will handle exceptions raised
        from queries, catch, log, and raise dbt exceptions it knows how to handle.
        """
        try:
            yield
        except Exception as exc:
            logger.debug("Error running SQL: {}".format(sql))
            logger.debug(str(exc))
            logger.debug("Rolling back transaction.")
            self.rollback_if_open()
            if isinstance(exc, DbtRuntimeError):
                # during a sql query, an internal to dbt exception was raised.
                # this sounds a lot like a signal handler and probably has
                # useful information, so raise it without modification.
                raise
            raise DbtRuntimeError(str(exc))

    @classmethod
    def open(cls, connection):
        if connection.state == "open":
            logger.debug("Connection is already open, skipping open.")
            return connection

        credentials = connection.credentials
        kwargs = {}

        kwargs["hostname"] = credentials.hostname
        kwargs["port"] = credentials.port
        kwargs["namespace"] = credentials.database
        kwargs["username"] = credentials.username
        kwargs["password"] = credentials.password

        check_driver(credentials)
        try:
            connection.handle = _dbapi().connect(**kwargs)
            connection.state = "open"
        except Exception as e:
            raise FailedToConnectError(str(e))

        return connection

    @classmethod
    def get_response(cls, cursor) -> AdapterResponse:
        """
        Gets a cursor object and returns adapter-specific information
        about the last executed command generally a AdapterResponse ojbect
        that has items such as code, rows_affected,etc. can also just be a string ex. "OK"
        if your cursor does not offer rich metadata.
        """
        code = "SUCCESS"
        num_rows = 0

        if cursor is not None and cursor.rowcount is not None:
            num_rows = cursor.rowcount

        return AdapterResponse(
            _message="{} {}".format(code, num_rows), rows_affected=num_rows, code=code
        )

    def cancel(self, connection):
        """
        Gets a connection object and attempts to cancel any ongoing queries.
        """
        connection.handle.close()

    def add_begin_query(self):
        return self.add_query("START TRANSACTION", auto_begin=False)

    def add_query(
        self,
        sql: str,
        auto_begin: bool = True,
        bindings: Optional[Any] = None,
        abridge_sql_log: bool = False,
        retryable_exceptions: Tuple[Type[Exception], ...] = tuple(),
        retry_limit: int = 1,
    ) -> Tuple[Connection, Any]:
        connection = self.get_thread_connection()
        if auto_begin and connection.transaction_open is False:
            self.begin()
        fire_event(ConnectionUsed(conn_type=self.TYPE, conn_name=connection.name))

        with self.exception_handler(sql):
            if abridge_sql_log:
                log_sql = "{}...".format(sql[:512])
            else:
                log_sql = sql

            fire_event(SQLQuery(conn_name=connection.name, sql=log_sql))
            pre = time.time()

            sql = sql.strip()
            if sql.endswith(";"):
                sql = sql[0:-1]

            cursor = connection.handle.cursor()
            many = (
                bindings
                and (isinstance(bindings, list) or isinstance(bindings, tuple))
                and len(bindings) > 0
                and (isinstance(bindings[0], list) or isinstance(bindings[0], tuple))
            )
            if many:
                cursor.executemany(sql, bindings)
            elif bindings is None:
                cursor.execute(sql)
            else:
                cursor.execute(sql, bindings)

            fire_event(
                SQLQueryStatus(
                    status=str(self.get_response(cursor)),
                    elapsed=round((time.time() - pre), 2),
                )
            )

            return connection, cursor

    @classmethod
    def process_results(cls, column_names, rows):
        # intersystems-irispython 5.x returns DataRow proxies bound to the cursor;
        # dbt reads results after the cursor is released. Copy values out first.
        return super().process_results(column_names, [tuple(r) for r in rows])

    @classmethod
    def data_type_code_to_name(cls, type_code: Union[int, str]) -> str:
        if isinstance(type_code, int):
            return _dbapi().SQLType(type_code).name
        return f"unknown type_code {type_code}"
