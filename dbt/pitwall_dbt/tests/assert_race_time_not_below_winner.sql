-- BUSINESS RULE: nobody can finish a race FASTER than the winner.
-- Without the repair in stg_fastf1_results (winner time + gap), every non-winner had a "race time"
-- of a few seconds (the gap). This test catches it if it ever comes back.
select r.race_id, r.driver_code, r.race_time_s, w.race_time_s as winner_time_s
from {{ ref('stg_fastf1_results') }} r
join {{ ref('stg_fastf1_results') }} w
  on w.race_id = r.race_id and w.session = 'R' and w.position = 1
where r.session = 'R' and r.race_time_s < w.race_time_s
