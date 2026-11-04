-- FastF1 (D) per race: practice pace per driver, safety cars, measured rain. Small and readable.
with pace as (
    select {{ race_id('season', 'round') }} as race_id, driver_code,
           min(try_to_double(best_lap_s)) as best_practice_lap_s
    from {{ source('bronze', 'fastf1_laps_summary') }}
    where session in ('FP1', 'FP2', 'FP3')
    group by 1, 2
),
fastest as (
    select race_id, min(best_practice_lap_s) as fastest_s from pace group by 1
)
select p.race_id, p.driver_code, p.best_practice_lap_s,
       p.best_practice_lap_s / f.fastest_s - 1 as practice_gap_pct      -- 0.01 = 1 % slower than the best
from pace p join fastest f using (race_id)
