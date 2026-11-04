-- FACT TABLE of the star schema. Grain: one row per race_id x driver_ref (tested in schema.yml).
with stops as (
    select race_id, driver_ref, count(*) as pit_stops from {{ ref('stg_pit_stops') }} group by 1, 2
)
select
    r.race_id, r.driver_ref, r.constructor_ref, c.circuit_ref,
    r.grid, q.quali_position, q.best_quali_s,
    r.finish_order, r.points, r.laps, r.status, r.is_classified, r.is_podium,
    iff(r.is_classified and r.grid > 0, r.grid - r.finish_order, null) as places_gained,
    s.pit_stops
from {{ ref('silver_results') }} r
join {{ ref('stg_races') }} c on c.race_id = r.race_id
left join {{ ref('stg_qualifying') }} q on q.race_id = r.race_id and q.driver_ref = r.driver_ref
left join stops s on s.race_id = r.race_id and s.driver_ref = r.driver_ref
