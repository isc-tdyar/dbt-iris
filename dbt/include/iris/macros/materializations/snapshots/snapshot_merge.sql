{#
  dbt's default is one MERGE. Here it is an UPDATE then an INSERT, which also runs on servers
  without MERGE: close the current rows the staging table updates or deletes, then insert its
  'insert' rows whose scd_id the target does not have yet (MERGE's "when not matched").
#}
{% macro iris__snapshot_merge_sql(target, source, insert_cols) -%}

    {%- set insert_cols_csv = insert_cols | join(', ') -%}
    {%- set columns = config.get("snapshot_table_column_names") or get_snapshot_table_column_names() -%}
    {%- set dest_valid_to = (target ~ "." ~ columns.dbt_valid_to) | trim -%}

    {% set update_sql %}
    update {{ target }}
    set {{ columns.dbt_valid_to }} = DBT_INTERNAL_SOURCE.{{ columns.dbt_valid_to }}
    from {{ source }} as DBT_INTERNAL_SOURCE
    where DBT_INTERNAL_SOURCE.{{ columns.dbt_scd_id }} = {{ target }}.{{ columns.dbt_scd_id }}
      and DBT_INTERNAL_SOURCE.dbt_change_type in ('update', 'delete')
    {% if config.get("dbt_valid_to_current") %}
      and ({{ equals(dest_valid_to, config.get('dbt_valid_to_current') | trim) }} or {{ dest_valid_to }} is null)
    {% else %}
      and {{ dest_valid_to }} is null
    {% endif %}
    {% endset %}

    {% do adapter.add_query(update_sql, auto_begin=False) %}

    insert into {{ target }} ({{ insert_cols_csv }})
    select {% for column in insert_cols -%}
        DBT_INTERNAL_SOURCE.{{ column }} {%- if not loop.last %}, {%- endif %}
    {%- endfor %}
    from {{ source }} as DBT_INTERNAL_SOURCE
    where DBT_INTERNAL_SOURCE.dbt_change_type = 'insert'
      and not exists (
        select 1 from {{ target }} as DBT_INTERNAL_DEST
        where DBT_INTERNAL_DEST.{{ columns.dbt_scd_id }} = DBT_INTERNAL_SOURCE.{{ columns.dbt_scd_id }}
      )

{% endmacro %}
