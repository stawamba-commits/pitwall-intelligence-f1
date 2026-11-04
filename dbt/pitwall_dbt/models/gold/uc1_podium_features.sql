-- UC1 · Podium prediction: one row per race x driver with the model's inputs.
-- Past races (with the answer is_podium) are used to train and backtest; the next race (is_next_race,
-- is_podium = null) is what the model scores. Every "form" feature only looks at EARLIER races
-- (rows ... 1 preceding): no information from the race itself leaks into its own prediction.
with next_race as (
    select * from {{ ref('dim_race') }} where is_next_race
),
history as (
    select f.race_id, f.driver_ref, f.constructor_ref, f.circuit_ref, r.race_date, r.season,
           f.grid, f.best_quali_s, f.finish_order, f.points, f.is_podium, false as is_next_race
    from {{ ref('fact_race_result') }} f
    join {{ ref('dim_race') }} r on r.race_id = f.race_id
    where r.is_completed and r.season >= {{ var('first_season') }}
),
next_entrants as (
    -- qualifying of the next race as soon as it exists (grid known) ...
    select q.driver_ref, q.constructor_ref, q.quali_position as grid, q.best_quali_s
    from {{ ref('stg_qualifying') }} q join next_race n on n.race_id = q.race_id
    union all
    -- ... otherwise the drivers of the last race (same entry list), grid still unknown
    select f.driver_ref, f.constructor_ref, null, null
    from {{ ref('fact_race_result') }} f
    where f.race_id = (select max_by(race_id, race_date) from {{ ref('dim_race') }} where is_completed)
      and not exists (select 1 from {{ ref('stg_qualifying') }} q join next_race n on n.race_id = q.race_id)
),
spine as (
    select * from history
    union all
    select n.race_id, e.driver_ref, e.constructor_ref, n.circuit_ref, n.race_date, n.season,
           e.grid, e.best_quali_s, null, null, null, true
    from next_entrants e cross join next_race n
),
team_form as (
    select race_id, constructor_ref,
           avg(team_points) over (partition by constructor_ref order by race_date
                                  rows between 5 preceding and 1 preceding) as team_avg_points_5
    from (select race_id, constructor_ref, race_date, sum(points) as team_points
          from spine group by 1, 2, 3)
)
select
    s.race_id, s.season, s.race_date, s.driver_ref, s.constructor_ref, s.circuit_ref, s.is_next_race,
    s.grid,
    s.best_quali_s / min(s.best_quali_s) over (partition by s.race_id) - 1          as quali_gap_pct,
    avg(s.finish_order) over (partition by s.driver_ref order by s.race_date
                              rows between 5 preceding and 1 preceding)            as driver_avg_finish_5,
    avg(s.finish_order) over (partition by s.driver_ref, s.circuit_ref order by s.race_date
                              rows between unbounded preceding and 1 preceding)    as driver_avg_finish_circuit,
    t.team_avg_points_5,
    p.practice_gap_pct,
    w.is_wet_race,
    s.is_podium
from spine s
left join team_form t on t.race_id = s.race_id and t.constructor_ref = s.constructor_ref
left join {{ ref('dim_driver') }} d on d.driver_ref = s.driver_ref
left join {{ ref('stg_practice_pace') }} p on p.race_id = s.race_id and p.driver_code = d.driver_code
left join {{ ref('dim_weather') }} w on w.race_id = s.race_id
