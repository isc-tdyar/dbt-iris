{#
  IRIS has no materialized views. A materialized_view model is built by the table materialization
  (the default: a real table, rebuilt on every dbt run and not refreshed in between) or, with
  iris_materialized_view_as: view, by the view materialization. One warning per run lists the
  models left on the default without the setting. on_configuration_change is ignored.
#}
{% materialization materialized_view, adapter='iris' %}
  {%- set mode = adapter.materialized_view_mode(config.get('iris_materialized_view_as')) -%}
  {%- set warning = adapter.materialized_view_warning(invocation_id, graph.nodes, selected_resources) -%}
  {%- if warning -%}
    {% do exceptions.warn(warning) %}
  {%- endif -%}
  {%- if mode == 'view' -%}
    {{ return(materialization_view_iris()) }}
  {%- else -%}
    {{ return(materialization_table_iris()) }}
  {%- endif -%}
{% endmaterialization %}
