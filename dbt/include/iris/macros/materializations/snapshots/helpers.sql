{#
  Snapshot helpers. They follow dbt-adapters' defaults (snapshot_meta_column_names,
  dbt_valid_to_current, multi-column unique_key, hard_deletes ignore / invalidate / new_record)
  with these IRIS differences:
  - IRIS rejects a WITH clause inside a derived table, so a model's leading CTEs (an ephemeral
    ref, for one) are hoisted above the wrapper in build_snapshot_table, and the staging query's
    nested CTEs are flattened by create_table_as.
  - dbt_valid_to is always computed as CAST(... AS TIMESTAMP), never copied from a column, so it
    has one type (%Library.TimeStamp) in the snapshot table and in every branch of the staging
    UNION. A column declared TIMESTAMP in DDL is a %Library.PosixTime, and IRIS 2026.2 copies a
    PosixTime value into a TimeStamp column without converting it. A CREATE TABLE AS whose
    UNION's first branch is a computed timestamp stores 'error 00:00:00' for a later branch's
    PosixTime column, and an INSERT ... SELECT of a PosixTime column into a TimeStamp column
    fails validation (SQLCODE -104). COALESCE also refuses to mix DATE and TIMESTAMP, so dbt's
    coalesce(nullif(updated_at, updated_at), ...) is not used either.
  - snapshot_get_time() is one server time per snapshot run, to the microsecond. IRIS's
    current_timestamp has whole seconds, and the check strategy hashes it into dbt_scd_id, so
    two runs within one second gave a changed row the scd_id of the row it replaces.
    current_timestamp(6) has microseconds but IRIS evaluates each occurrence in a statement
    separately, so a closed row's dbt_valid_to and its successor's dbt_valid_from would differ.
    The time is read once and kept on the snapshot's `model` dict, which every macro rendered
    for this node shares, like the transaction-constant now() that dbt's default relies on.
#}

{% macro iris__snapshot_get_time() -%}
  {%- if execute and model is mapping and model.get('resource_type') == 'snapshot' -%}
    {%- if '_iris_snapshot_time' not in model -%}
      {%- set now = run_query('select current_timestamp(6)').columns[0].values()[0] -%}
      {%- set now = now if now is string else now.strftime('%Y-%m-%d %H:%M:%S.%f') -%}
      {%- do model.update({'_iris_snapshot_time': now}) -%}
    {%- endif -%}
    cast('{{ model['_iris_snapshot_time'] }}' as timestamp)
  {%- else -%}
    current_timestamp(6)
  {%- endif -%}
{%- endmacro %}

{% macro iris__create_columns(relation, columns) %}
  {% for column in columns %}
    {% call statement() %}
      alter table {{ relation }} add column "{{ column.name }}" {{ column.data_type }}
    {% endcall %}
  {% endfor %}
{% endmacro %}

{% macro iris__get_true_sql() %}
    {{ return('1=1') }}
{% endmacro %}

{% macro iris_snapshot_valid_to_current(columns) -%}
    cast({{ config.get('dbt_valid_to_current') or 'null' }} as timestamp) as {{ columns.dbt_valid_to }}
{%- endmacro %}

{% macro iris__build_snapshot_table(strategy, sql) %}
    {% set columns = config.get('snapshot_table_column_names') or get_snapshot_table_column_names() %}
    {%- set parts = adapter.split_leading_ctes(sql) -%}
    {{ parts[0] }}
    select *,
        {{ strategy.scd_id }} as {{ columns.dbt_scd_id }},
        {{ strategy.updated_at }} as {{ columns.dbt_updated_at }},
        {{ strategy.updated_at }} as {{ columns.dbt_valid_from }},
        {{ iris_snapshot_valid_to_current(columns) }}
      {%- if strategy.hard_deletes == 'new_record' -%}
        , 'False' as {{ columns.dbt_is_deleted }}
      {% endif %}
    from (
        {{ parts[1] }}
    ) sbq

{% endmacro %}

{% macro iris__snapshot_staging_table(strategy, source_sql, target_relation) -%}
    {% set columns = config.get('snapshot_table_column_names') or get_snapshot_table_column_names() %}
    {% if strategy.hard_deletes == 'new_record' %}
        {% set new_scd_id = snapshot_hash_arguments([columns.dbt_scd_id, snapshot_get_time()]) %}
    {% endif %}
    {%- if config.get('dbt_valid_to_current') -%}
        {% set valid_to_current = config.get('dbt_valid_to_current') | trim %}
        {#- the condition for a current row of the snapshot table -#}
        {% set is_current %}
            ( {{ equals(columns.dbt_valid_to | trim, valid_to_current) }} or {{ columns.dbt_valid_to }} is null )
        {% endset %}
        {% set snapshotted_is_current = 'snapshotted_data.' ~ columns.dbt_valid_to ~ ' = ' ~ valid_to_current %}
    {%- else -%}
        {% set is_current = columns.dbt_valid_to ~ ' is null' %}
        {% set snapshotted_is_current = 'snapshotted_data.' ~ columns.dbt_valid_to ~ ' is null' %}
    {%- endif %}
    with snapshot_query as (

        {{ source_sql }}

    ),

    snapshotted_data as (

        select *, {{ unique_key_fields(strategy.unique_key) }}
        from {{ target_relation }}
        where {{ is_current }}

    ),

    insertions_source_data as (

        select *, {{ unique_key_fields(strategy.unique_key) }},
            {{ strategy.updated_at }} as {{ columns.dbt_updated_at }},
            {{ strategy.updated_at }} as {{ columns.dbt_valid_from }},
            {{ iris_snapshot_valid_to_current(columns) }},
            {{ strategy.scd_id }} as {{ columns.dbt_scd_id }}

        from snapshot_query
    ),

    updates_source_data as (

        select *, {{ unique_key_fields(strategy.unique_key) }},
            {{ strategy.updated_at }} as {{ columns.dbt_updated_at }},
            {{ strategy.updated_at }} as {{ columns.dbt_valid_from }},
            cast({{ strategy.updated_at }} as timestamp) as {{ columns.dbt_valid_to }}

        from snapshot_query
    ),

    {%- if strategy.hard_deletes == 'invalidate' or strategy.hard_deletes == 'new_record' %}

    deletes_source_data as (

        select *, {{ unique_key_fields(strategy.unique_key) }}
        from snapshot_query
    ),
    {% endif %}

    insertions as (

        select
            'insert' as dbt_change_type,
            source_data.*
          {%- if strategy.hard_deletes == 'new_record' -%}
            ,'False' as {{ columns.dbt_is_deleted }}
          {%- endif %}

        from insertions_source_data as source_data
        left outer join snapshotted_data
            on {{ unique_key_join_on(strategy.unique_key, "snapshotted_data", "source_data") }}
            where {{ unique_key_is_null(strategy.unique_key, "snapshotted_data") }}
            or ({{ unique_key_is_not_null(strategy.unique_key, "snapshotted_data") }} and (
               {{ strategy.row_changed }} {%- if strategy.hard_deletes == 'new_record' -%} or snapshotted_data.{{ columns.dbt_is_deleted }} = 'True' {% endif %}
            )

        )

    ),

    updates as (

        select
            'update' as dbt_change_type,
            source_data.*,
            snapshotted_data.{{ columns.dbt_scd_id }}
          {%- if strategy.hard_deletes == 'new_record' -%}
            , snapshotted_data.{{ columns.dbt_is_deleted }}
          {%- endif %}

        from updates_source_data as source_data
        join snapshotted_data
            on {{ unique_key_join_on(strategy.unique_key, "snapshotted_data", "source_data") }}
        where (
            {{ strategy.row_changed }}  {%- if strategy.hard_deletes == 'new_record' -%} or snapshotted_data.{{ columns.dbt_is_deleted }} = 'True' {% endif %}
        )
    )

    {%- if strategy.hard_deletes == 'invalidate' or strategy.hard_deletes == 'new_record' %}
    ,
    deletes as (

        select
            'delete' as dbt_change_type,
            source_data.*,
            {{ snapshot_get_time() }} as {{ columns.dbt_valid_from }},
            {{ snapshot_get_time() }} as {{ columns.dbt_updated_at }},
            {{ snapshot_get_time() }} as {{ columns.dbt_valid_to }},
            snapshotted_data.{{ columns.dbt_scd_id }}
          {%- if strategy.hard_deletes == 'new_record' -%}
            , snapshotted_data.{{ columns.dbt_is_deleted }}
          {%- endif %}
        from snapshotted_data
        left join deletes_source_data as source_data
            on {{ unique_key_join_on(strategy.unique_key, "snapshotted_data", "source_data") }}
            where {{ unique_key_is_null(strategy.unique_key, "source_data") }}

            {%- if strategy.hard_deletes == 'new_record' %}
            {#- leave the record's valid_to alone if its latest entry already marks it deleted #}
            and not (
                snapshotted_data.{{ columns.dbt_is_deleted }} = 'True'
                and {{ snapshotted_is_current }}
            )
            {%- endif %}
    )
    {%- endif %}

    {%- if strategy.hard_deletes == 'new_record' %}
        {% set snapshotted_cols = get_list_of_column_names(get_columns_in_relation(target_relation)) %}
        {% set source_col_names = get_columns_in_query(source_sql) %}
    ,
    deletion_records as (

        select
            'insert' as dbt_change_type,
            {%- for col_name in source_col_names -%}
            {%- if col_name in snapshotted_cols -%}
            snapshotted_data.{{ adapter.quote(col_name) }},
            {%- else -%}
            source_data.{{ adapter.quote(col_name) }},
            {%- endif -%}
            {% endfor -%}
            {%- if strategy.unique_key | is_list -%}
                {%- for key in strategy.unique_key -%}
            snapshotted_data.{{ key }} as dbt_unique_key_{{ loop.index }},
                {% endfor -%}
            {%- else -%}
            snapshotted_data.dbt_unique_key as dbt_unique_key,
            {% endif -%}
            {{ snapshot_get_time() }} as {{ columns.dbt_valid_from }},
            {{ snapshot_get_time() }} as {{ columns.dbt_updated_at }},
            cast(snapshotted_data.{{ columns.dbt_valid_to }} as timestamp) as {{ columns.dbt_valid_to }},
            {{ new_scd_id }} as {{ columns.dbt_scd_id }},
            'True' as {{ columns.dbt_is_deleted }}
        from snapshotted_data
        left join deletes_source_data as source_data
            on {{ unique_key_join_on(strategy.unique_key, "snapshotted_data", "source_data") }}
        where {{ unique_key_is_null(strategy.unique_key, "source_data") }}
        {#- do not insert another deletion record if the latest one already marks it deleted #}
        and not (
            snapshotted_data.{{ columns.dbt_is_deleted }} = 'True'
            and {{ snapshotted_is_current }}
        )

    )
    {%- endif %}

    select * from insertions
    union all
    select * from updates
    {%- if strategy.hard_deletes == 'invalidate' or strategy.hard_deletes == 'new_record' %}
    union all
    select * from deletes
    {%- endif %}
    {%- if strategy.hard_deletes == 'new_record' %}
    union all
    select * from deletion_records
    {%- endif %}

{%- endmacro %}
