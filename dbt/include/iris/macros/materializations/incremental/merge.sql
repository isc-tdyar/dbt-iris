{#
  delete+insert: delete the target rows that match a source row on unique_key, then insert the
  source. Matching is the same as the merge strategy's (iris__merge_match). 1.9.x matched with
  IFNULL(key, '') IN (...), which IRIS evaluates as no match for integer keys.
#}
{% macro iris__get_delete_insert_merge_sql(target, source, unique_key, dest_columns, incremental_predicates) -%}
    {%- set dest_cols_csv = get_quoted_csv(dest_columns | map(attribute="name")) -%}
    {% if unique_key %}
        {%- set match = iris__merge_match(unique_key, "DBT_INTERNAL_SOURCE", "DBT_INTERNAL_DEST") | join(" and ") -%}
        {% call statement('delete') -%}
            delete from {{ target }} as DBT_INTERNAL_DEST
            where exists (
                select 1 from {{ source }} as DBT_INTERNAL_SOURCE
                where {{ match }}
            )
            {%- if incremental_predicates %}
                {% for predicate in incremental_predicates %}
                    and {{ predicate }}
                {% endfor %}
            {%- endif -%}
        {%- endcall %}
    {% endif %}

    insert into {{ target }} ({{ dest_cols_csv }})
    select {{ dest_cols_csv }}
    from {{ source }}

{%- endmacro %}
