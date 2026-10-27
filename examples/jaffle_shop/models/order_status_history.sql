{#-
  An incremental model: the first run builds the table from every order; later runs
  only add orders newer than the newest one already in the table.
#}
{{ config(materialized='incremental', unique_key='order_id') }}

select
    order_id,
    customer_id,
    order_date,
    status
from {{ ref('stg_orders') }}

{% if is_incremental() %}
where order_date > (select max(order_date) from {{ this }})
{% endif %}
