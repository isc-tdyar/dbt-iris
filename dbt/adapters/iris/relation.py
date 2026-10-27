from dataclasses import dataclass, field
from typing import Optional
from typing import FrozenSet

from dbt.adapters.base.relation import BaseRelation, Policy
from dbt.adapters.contracts.relation import ComponentName, RelationType
from dbt_common.utils import filter_null_values
from dbt.exceptions import DbtRuntimeError


@dataclass
class IRISQuotePolicy(Policy):
    database: bool = False
    schema: bool = True
    identifier: bool = True


@dataclass
class IRISIncludePolicy(Policy):
    database: bool = False
    schema: bool = True
    identifier: bool = True


@dataclass(frozen=True, eq=False, repr=False)
class IRISRelation(BaseRelation):
    renameable_relations: FrozenSet[RelationType] = field(
        default_factory=lambda: frozenset(
            {
                RelationType.Table,
                RelationType.View,
            }
        )
    )
    replaceable_relations: FrozenSet[RelationType] = field(
        default_factory=lambda: frozenset(
            {
                RelationType.View,
                RelationType.Table,
            }
        )
    )

    quote_policy: Policy = field(default_factory=lambda: IRISQuotePolicy())
    include_policy: Policy = field(default_factory=lambda: IRISIncludePolicy())

    def _render_event_time_filtered(self, event_time_filter) -> str:
        """Microbatch input filter with IRIS timestamp literals.

        dbt's default writes the bounds as strings with a timezone offset, which an IRIS
        TIMESTAMP comparison does not match. Bounds are in UTC, as dbt computes them.
        """

        def literal(value) -> str:
            return f"cast('{value.strftime('%Y-%m-%d %H:%M:%S')}' as timestamp)"

        field_name = event_time_filter.field_name
        parts = []
        if event_time_filter.start:
            parts.append(f"{field_name} >= {literal(event_time_filter.start)}")
        if event_time_filter.end:
            parts.append(f"{field_name} < {literal(event_time_filter.end)}")
        return " and ".join(parts)

    def __repr__(self) -> str:
        return "<{} {} {}>".format(self.__class__.__name__, self.type, self.render())

    def matches(
        self,
        database: Optional[str] = None,
        schema: Optional[str] = None,
        identifier: Optional[str] = None,
    ) -> bool:
        search = filter_null_values(
            {
                ComponentName.Database: database,
                ComponentName.Schema: schema,
                ComponentName.Identifier: identifier,
            }
        )

        if not search:
            # nothing was passed in
            raise DbtRuntimeError("Tried to match relation, but no search path was passed!")

        exact_match = True
        approximate_match = True

        for k, v in search.items():
            if not self._is_exactish_match(k, v):
                exact_match = False
            if str(self.path.get_lowered_part(k)).strip(self.quote_character) != v.lower().strip(
                self.quote_character
            ):
                approximate_match = False

        # if approximate_match and not exact_match:
        #     target = self.create(database=database, schema=schema, identifier=identifier)
        #     dbt.exceptions.approximate_relation_match(target, self)

        return exact_match or approximate_match
