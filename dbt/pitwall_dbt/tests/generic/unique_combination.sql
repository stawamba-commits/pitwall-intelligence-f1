-- Generic KEY test without any package (course: dbt_utils_free_unique_combination.sql):
-- the grain of the model (e.g. race_id x driver_ref) must be unique. Returns the duplicated keys.
{% test unique_combination(model, columns) %}
select {{ columns | join(', ') }}, count(*) as n
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}
