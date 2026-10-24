{% macro iris__get_incremental_default_sql(arg_dict) %}

  {% if arg_dict["unique_key"] %}
    {% do return(get_incremental_delete_insert_sql(arg_dict)) %}
  {% else %}
    {% do return(get_incremental_append_sql(arg_dict)) %}
  {% endif %}

{% endmacro %}


{% macro iris__get_incremental_append_sql(arg_dict) %}

  {% do return(get_insert_into_sql(arg_dict["target_relation"], arg_dict["temp_relation"], arg_dict["dest_columns"])) %}

{% endmacro %}

{% macro get_insert_into_sql(target_relation, temp_relation, dest_columns) %}

    {%- set dest_cols_csv = get_quoted_csv(dest_columns | map(attribute="name")) -%}

    insert into {{ target_relation }} ({{ dest_cols_csv }})
      select {{ dest_cols_csv }}
      from {{ temp_relation }}

{% endmacro %}


{#
  The microbatch strategy: replace the target rows in the batch's event_time window, then insert
  the batch. dbt has already filtered the batch's inputs to the same window.
#}
{% macro iris__get_incremental_microbatch_sql(arg_dict) %}
  {%- set target = arg_dict["target_relation"] -%}
  {%- set source = arg_dict["temp_relation"] -%}
  {%- set dest_columns = arg_dict["dest_columns"] -%}
  {%- set predicates = [] if arg_dict.get("incremental_predicates") is none else [] + arg_dict.get("incremental_predicates") -%}
  {%- set event_time = model.config.event_time -%}
  {%- if model.batch and model.batch.event_time_start -%}
    {%- do predicates.append(event_time ~ " >= cast('" ~ model.batch.event_time_start.strftime("%Y-%m-%d %H:%M:%S") ~ "' as timestamp)") -%}
  {%- endif -%}
  {%- if model.batch and model.batch.event_time_end -%}
    {%- do predicates.append(event_time ~ " < cast('" ~ model.batch.event_time_end.strftime("%Y-%m-%d %H:%M:%S") ~ "' as timestamp)") -%}
  {%- endif -%}

  {% if predicates %}
    {% set delete_sql %}
    delete from {{ target }} where {{ predicates | join(" and ") }}
    {% endset %}
    {% do adapter.add_query(delete_sql, auto_begin=False) %}
  {% endif %}

  {{ return(get_insert_into_sql(target, source, dest_columns)) }}
{% endmacro %}
