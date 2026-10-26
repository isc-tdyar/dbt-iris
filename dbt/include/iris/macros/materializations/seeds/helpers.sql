{% macro iris__create_csv_table(model, agate_table) %}
  {%- set column_override = model['config'].get('column_types', {}) -%}
  {%- set quote_seed_column = model['config'].get('quote_columns', None) -%}
  {%- set seed_collation = iris_seed_collation(model['config'].get('iris_collation')) -%}

  {% set sql %}
    /* test create table */
    create table {{ this.render() }} (
        {%- for col_name in agate_table.column_names -%}
            {%- set inferred_type = adapter.convert_type(agate_table, loop.index0) -%}
            {%- set type = iris_seed_column_type(column_override.get(col_name, inferred_type), seed_collation) -%}
            {%- set column_name = (col_name | string) -%}
            {{ adapter.quote_seed_column(column_name, quote_seed_column) }} {{ type }} {%- if not loop.last %}, {%- endif -%}
        {%- endfor -%}
    )
  {% endset %}

  {% call statement('_') -%}
    {{ sql }}
  {%- endcall %}

  {{ return(sql) }}
{% endmacro %}

{#
  iris_collation (seeds): default or exact. IRIS string columns default to a case-insensitive
  collation, so GROUP BY returns the upper-case form and 'female' = 'Female'. exact gives the
  seed's string columns %EXACT collation: they keep their case and compare case-sensitively, as on
  other warehouses, and tables built from the seed inherit it. Written as macros, not adapter
  methods, so dbt Fusion runs them as they are.
#}
{% macro iris_seed_collation(setting) -%}
  {%- if setting is none -%}
    {{ return('default') }}
  {%- endif -%}
  {%- set mode = setting | string | trim | lower if setting is string else setting -%}
  {%- if mode not in ('default', 'exact') -%}
    {{ exceptions.raise_compiler_error("iris_collation must be one of 'default', 'exact', got " ~ setting) }}
  {%- endif -%}
  {{ return(mode) }}
{%- endmacro %}

{% macro iris_seed_column_type(data_type, collation) -%}
  {#- VARCHAR-family types take a collation; TEXT and LONGVARCHAR are streams and do not. -#}
  {%- set t = data_type | lower | trim -%}
  {%- set is_string = t.startswith('varchar') or t.startswith('char') or t.startswith('nvarchar')
                      or t.startswith('nchar') -%}
  {%- if collation == 'exact' and is_string and 'collate' not in t -%}
    {{ return(data_type ~ ' COLLATE %EXACT') }}
  {%- endif -%}
  {{ return(data_type) }}
{%- endmacro %}
