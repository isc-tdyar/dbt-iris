{#
  The merge strategy.

  A server that accepts MERGE INTO gets dbt's standard MERGE. Otherwise the merge runs as two
  statements in the model's transaction: an UPDATE of the target rows that match a source row on
  unique_key, then an INSERT of the source rows that match nothing. Neither needs a primary key
  or unique index on the target, which a table built with CREATE TABLE AS does not have.

  Matching follows dbt's default MERGE: a single key matches NULL to NULL (dbt's equals()),
  composite keys use plain equality, and incremental_predicates narrow the match.
#}
{% macro iris__get_merge_sql(target, source, unique_key, dest_columns, incremental_predicates=none) -%}
    {%- if adapter.supports_merge() -%}
        {{ default__get_merge_sql(target, source, unique_key, dest_columns, incremental_predicates) }}
    {%- else -%}
        {{ iris__get_update_insert_merge_sql(target, source, unique_key, dest_columns, incremental_predicates) }}
    {%- endif -%}
{%- endmacro %}


{% macro iris__merge_match(unique_key, source_alias, target_alias) -%}
    {%- set matches = [] -%}
    {%- if unique_key is sequence and unique_key is not mapping and unique_key is not string -%}
        {%- for key in unique_key -%}
            {%- do matches.append(source_alias ~ "." ~ key ~ " = " ~ target_alias ~ "." ~ key) -%}
        {%- endfor -%}
    {%- else -%}
        {%- set s = source_alias ~ "." ~ unique_key -%}
        {%- set t = target_alias ~ "." ~ unique_key -%}
        {%- do matches.append("(" ~ s ~ " = " ~ t ~ " or (" ~ s ~ " is null and " ~ t ~ " is null))") -%}
    {%- endif -%}
    {{ return(matches) }}
{%- endmacro %}


{#- Quoted the way get_quoted_csv quotes dest_columns; dbt's get_merge_update_columns uses the
    column class's quote character, which IRIS does not accept. -#}
{% macro iris__merge_update_columns(merge_update_columns, merge_exclude_columns, dest_columns) -%}
    {%- if merge_update_columns -%}
        {%- set names = merge_update_columns | list -%}
    {%- else -%}
        {%- set names = [] -%}
        {%- set excluded = (merge_exclude_columns or []) | map("lower") | list -%}
        {%- for column in dest_columns -%}
            {%- if column.name | lower not in excluded -%}{%- do names.append(column.name) -%}{%- endif -%}
        {%- endfor -%}
    {%- endif -%}
    {%- set quoted = [] -%}
    {%- for name in names -%}{%- do quoted.append(adapter.quote(name)) -%}{%- endfor -%}
    {{ return(quoted) }}
{%- endmacro %}


{% macro iris__get_update_insert_merge_sql(target, source, unique_key, dest_columns, incremental_predicates=none) -%}
    {%- set dest_cols_csv = get_quoted_csv(dest_columns | map(attribute="name")) -%}
    {%- set sql_header = config.get('sql_header', none) -%}
    {%- set predicates = [] + (incremental_predicates or []) -%}

    {%- if unique_key -%}
        {%- set merge_update_columns = config.get('merge_update_columns') -%}
        {%- set merge_exclude_columns = config.get('merge_exclude_columns') -%}
        {%- set update_columns = iris__merge_update_columns(merge_update_columns, merge_exclude_columns, dest_columns) -%}
        {%- set match = (iris__merge_match(unique_key, "DBT_INTERNAL_SOURCE", "DBT_INTERNAL_DEST") + predicates) | join(" and ") -%}

        {%- if update_columns | length > 0 -%}
            {% set update_sql %}
            update {{ target }} as DBT_INTERNAL_DEST
            set {% for column_name in update_columns -%}
                {{ column_name }} = DBT_INTERNAL_SOURCE.{{ column_name }}
                {%- if not loop.last %}, {% endif %}
            {%- endfor %}
            from {{ source }} as DBT_INTERNAL_SOURCE
            where {{ match }}
            {% endset %}
            {% do adapter.add_query(update_sql, auto_begin=False) %}
        {%- endif %}
    {%- endif %}

    {{ sql_header if sql_header is not none }}
    insert into {{ target }} ({{ dest_cols_csv }})
    select {{ dest_cols_csv }} from {{ source }}
    {%- if unique_key %} as DBT_INTERNAL_SOURCE
    where not exists (
        select 1 from {{ target }} as DBT_INTERNAL_DEST
        where {{ match }}
    )
    {%- endif %}

{%- endmacro %}
