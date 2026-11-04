-- UC3 · Pit strategy: per circuit, how many stops the classified drivers made over the last 3 seasons,
-- and which tyre compounds were used (FastF1). The next race's circuit is flagged for the TV analyst.
with recent as (
    select f.circuit_ref, f.race_id, f.pit_stops
    from {{ ref('fact_race_result') }} f
    join {{ ref('dim_race') }} r on r.race_id = f.race_id
    where r.is_completed and f.is_classified and f.pit_stops is not null
      and r.season >= year({{ run_date() }}) - 3
),
compounds as (
    select r.circuit_ref, listagg(distinct s.compound, ', ') within group (order by s.compound) as compounds_used
    from {{ ref('stg_tyre_stints') }} s
    join {{ ref('stg_races') }} r on r.race_id = s.race_id
    group by 1
)
select
    rc.circuit_ref,
    count(distinct rc.race_id)               as races,
    round(avg(rc.pit_stops), 2)              as avg_stops,
    mode(rc.pit_stops)                       as usual_stops,
    c.compounds_used,
    rc.circuit_ref = (select circuit_ref from {{ ref('dim_race') }} where is_next_race) as is_next_race_circuit
from recent rc
left join compounds c on c.circuit_ref = rc.circuit_ref
group by rc.circuit_ref, c.compounds_used
