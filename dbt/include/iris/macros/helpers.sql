{% macro iris__load_csv_rows(model, agate_table) %}
  {#
    dbt v2 (dbt Fusion) reports a 2.x dbt_version and loads the seed with one ADBC bulk ingest
    through the IRIS ADBC driver; dbt-core (1.x) inserts it in batches below. The same gate as
    dbt-bigquery's bigquery__load_csv_rows in dbt v2.
  #}
  {% if dbt_version.startswith('2.') %}
    {{ adapter.load_dataframe(
        model['database'],
        model['schema'],
        model['alias'],
        adapter.get_seed_file_path(model),
        agate_table,
        model['config'].get('column_types', {}),
        model['config'].get('delimiter', ','),
    ) }}
    {{ return('') }}
  {% endif %}

  {% set batch_size = get_batch_size() %}

  {% set cols_sql = get_seed_column_quoted_csv(model, agate_table.column_names) %}
  {% set bindings = [] %}

  {% set statements = [] %}

  {% for chunk in agate_table.rows | batch(batch_size) %}
      {% set bindings = [] %}

      {% for row in chunk %}
          {% do bindings.append(row[:]) %}
      {% endfor %}

      {% set sql %}
          insert into {{ this.render() }} ({{ cols_sql }}) values
          ({%- for column in agate_table.column_names -%}
              {{ get_binding_char() }}
              {%- if not loop.last%},{%- endif %}
          {%- endfor -%})
      {% endset %}

      {% do adapter.add_query(sql, bindings=bindings, abridge_sql_log=True) %}

      {% if loop.index0 == 0 %}
          {% do statements.append(sql) %}
      {% endif %}
  {% endfor %}

  {# Return SQL so we can render it out into the compiled files #}
  {{ return(statements[0]) }}
{% endmacro %}
