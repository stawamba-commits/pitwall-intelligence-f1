-- FastF1 (D) session classification.
-- DATA BUG found while profiling the source: in FastF1 race results, "Time" is the TOTAL time only
-- for the winner; for everyone else it is the GAP to the winner (e.g. 39.669 s). Here we repair it:
--   race_time_s = winner time + gap.   tests/assert_race_time_not_below_winner.sql checks the rule.
with typed as (
    select
        {{ race_id('season', 'round') }} as race_id, session, driver_code, team,
        try_to_double({{ na('position') }})::int as position,
        try_to_double({{ na('time_s') }})                  as time_raw_s,
        status
    from {{ source('bronze', 'fastf1_results') }}
)
select
    t.*,
    case when t.session != 'R' then null
         when t.position = 1   then t.time_raw_s
         else w.time_raw_s + t.time_raw_s end as race_time_s
from typed t
left join typed w on w.race_id = t.race_id and w.session = t.session and w.position = 1
