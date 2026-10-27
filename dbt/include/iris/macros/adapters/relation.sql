{% macro iris__suffix() %}
  {{ return("__" ~ (invocation_id | replace("-",""))) }}
{% endmacro %}

{% macro iris__make_intermediate_relation(base_relation, suffix) %}
    {{ return(default__make_temp_relation(base_relation, iris__suffix())) }}
{% endmacro %}

{% macro iris__make_temp_relation(base_relation, suffix) %}
    {%- set temp_identifier = base_relation.identifier ~ iris__suffix() -%}
    {%- set temp_relation = base_relation.incorporate(
                                path={"identifier": temp_identifier}) -%}

    {{ return(temp_relation) }}
{% endmacro %}

{% macro iris__make_backup_relation(base_relation, backup_relation_type, suffix) %}
    {%- set backup_identifier = base_relation.identifier ~ "__dbt_backup" ~ iris__suffix() -%}
    {%- set backup_relation = base_relation.incorporate(
                                  path={"identifier": backup_identifier},
                                  type=backup_relation_type) -%}
    {{ return(backup_relation) }}
{% endmacro %}
