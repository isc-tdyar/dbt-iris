{#
  IRIS has no materialized views, so a materialized_view model is built by the table
  materialization: a real table, rebuilt on every dbt run and not refreshed in between. This lets
  projects written for other warehouses run unchanged. on_configuration_change has nothing to
  apply to a table and is ignored.
#}
{% materialization materialized_view, adapter='iris' %}
  {% do exceptions.warn(
      "dbt-iris: IRIS has no materialized views; " ~ this ~ " is built as a table, "
      ~ "rebuilt on each dbt run and not refreshed automatically."
  ) %}
  {{ return(materialization_table_iris()) }}
{% endmaterialization %}
