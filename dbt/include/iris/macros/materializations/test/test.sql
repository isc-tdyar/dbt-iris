{% macro iris__get_test_sql(main_sql, fail_calc, warn_if, error_if, limit) -%}
    {#- IRIS rejects a WITH clause inside a derived table. Ephemeral models are
        injected as CTEs at the top of main_sql, so hoist them above the wrapper. -#}
    {%- set parts = adapter.split_leading_ctes(main_sql) -%}
    {%- set main_sql = parts[1] -%}
    {{ parts[0] }}
    select
      {{ fail_calc }} as failures,
      case
        when {{ fail_calc }} {{ warn_if | replace("!=","<>") }} then 'true'
        else 'false'
      end as should_warn,
      case
        when {{ fail_calc }} {{ error_if | replace("!=","<>") }} then 'true'
        else 'false'
      end as should_error
    from (
      {{ main_sql }}
      {{ "limit " ~ limit if limit != none }}
    ) dbt_internal_test
{%- endmacro %}
