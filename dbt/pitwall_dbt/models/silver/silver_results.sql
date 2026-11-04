-- Clean race results. Grain: one row per race_id x driver_ref.
select
    race_id, season, round, driver_ref, driver_code, driver_name, driver_dob,
    constructor_ref, constructor_name,
    grid, finish_order, points, laps, status, race_time_ms,
    {{ is_finished('status') }}       as is_classified,
    finish_order <= 3                  as is_podium,
    source
from {{ ref('int_results_checked') }}
where array_size(problems) = 0
