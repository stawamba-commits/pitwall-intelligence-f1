{# Reusable cleaning rules (course: macros/cleaning.sql) #}

{# Kaggle writes missing values as \N, the APIs as empty strings: both become NULL #}
{% macro na(col) -%}
    nullif(nullif(trim({{ col }}), '\\N'), '')
{%- endmacro %}

{# "1:29.179" -> 89.179 seconds ; "23.456" -> 23.456 #}
{% macro lap_seconds(col) -%}
    iff(contains({{ na(col) }}, ':'),
        try_to_number(split_part({{ na(col) }}, ':', 1)) * 60 + try_to_double(split_part({{ na(col) }}, ':', 2)),
        try_to_double({{ na(col) }}))
{%- endmacro %}

{# One id for a race in every source: season-round, e.g. 2026-21 #}
{% macro race_id(season, round) -%}
    ({{ season }}::string || '-' || lpad({{ round }}::string, 2, '0'))
{%- endmacro %}

{# The date comes from the run (Airflow passes {{ ds }}), never from "today": backfills work #}
{% macro run_date() -%}
    '{{ var("run_date", run_started_at.strftime("%Y-%m-%d")) }}'::date
{%- endmacro %}

{# Classified at the finish: finished on the lead lap or lapped ("+1 Lap", "Lapped") #}
{% macro is_finished(status) -%}
    ({{ status }} in ('Finished', 'Lapped') or {{ status }} like '+%Lap%')
{%- endmacro %}
