-- UC5 · Safety-car risk: share of races with at least one safety car (or VSC) per circuit,
-- over the last 5 seasons (FastF1 timing exists from 2018). Media use it for the race preview.
select
    r.circuit_ref,
    count(*)                                                        as races,
    count_if(e.safety_cars > 0)                                     as races_with_safety_car,
    count_if(e.safety_cars > 0 or e.virtual_safety_cars > 0)        as races_with_sc_or_vsc,
    round(races_with_sc_or_vsc / races, 2)                          as sc_or_vsc_rate,
    r.circuit_ref = (select circuit_ref from {{ ref('dim_race') }} where is_next_race) as is_next_race_circuit
from {{ ref('stg_race_events') }} e
join {{ ref('dim_race') }} r on r.race_id = e.race_id
where r.is_completed and r.season >= year({{ run_date() }}) - 5
group by r.circuit_ref
