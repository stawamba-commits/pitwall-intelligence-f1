-- UC2 · Places gained: grid - finish for every classified driver (positive = overtook).
-- Retirements and pit-lane starts (grid 0) are excluded. Grain: race_id x driver_ref.
select
    r.season, r.round, r.race_name, r.race_date, f.race_id, f.circuit_ref,
    f.driver_ref, d.driver_name, c.constructor_name,
    f.grid, f.finish_order, f.places_gained,
    coalesce(w.is_wet_race, false) as is_wet_race
from {{ ref('fact_race_result') }} f
join {{ ref('dim_race') }} r on r.race_id = f.race_id
join {{ ref('dim_driver') }} d on d.driver_ref = f.driver_ref
join {{ ref('dim_constructor') }} c on c.constructor_ref = f.constructor_ref
left join {{ ref('dim_weather') }} w on w.race_id = f.race_id
where f.places_gained is not null
