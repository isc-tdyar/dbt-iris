{% macro iris__get_columns_in_query(select_sql) %}
    {#- IRIS rejects WITH inside a derived table; hoist leading CTEs above the wrapper. -#}
    {%- set parts = adapter.split_leading_ctes(select_sql) -%}
    {% call statement('get_columns_in_query', fetch_result=True, auto_begin=False) -%}
        {{ parts[0] }}
        select top 0 * from (
            {{ parts[1] }}
        ) as __dbt_sbq
        where 1=0
    {% endcall %}

    {{ return(load_result('get_columns_in_query').table.columns | map(attribute='name') | list) }}
{% endmacro %}

{% macro iris__get_empty_subquery_sql(select_sql, select_sql_header=none) %}
    {%- if select_sql_header is not none -%}
    {{ select_sql_header }}
    {%- endif -%}
    {%- set parts = adapter.split_leading_ctes(select_sql) -%}
    {{ parts[0] }}
    select top 0 * from (
        {{ parts[1] }}
    ) as __dbt_sbq
    where 1=0
{% endmacro %}

{% macro iris__alter_relation_add_remove_columns(relation, add_columns, remove_columns) %}

  {% if add_columns %}

    {% for column in add_columns %}
      {% set sql -%}
          alter {{ relation.type }} {{ relation }} add column {{ column.name }} {{ column.data_type }}
      {% endset %}
      {% do run_query(sql) %}
    {% endfor %}

  {% endif %}

  {% if remove_columns %}

    {% for column in remove_columns %}
      {% set sql -%}
          alter {{ relation.type }} {{ relation }} drop column {{ column.name }}
      {% endset %}
      {% do run_query(sql) %}
    {% endfor %}

  {% endif %}

  {% if add_columns or remove_columns %}
    {{ iris_purge_cached_queries(relation) }}
  {% endif %}

{% endmacro %}
