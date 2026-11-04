-- FastF1 (D) per race: neutralisations (track status codes 4 = safety car, 6 = VSC, 5 = red flag),
-- rain measured at the track, and the number of pit stops of each driver (tyre stints - 1).
with status as (
    select {{ race_id('season', 'round') }} as race_id,
           count_if(status = '4') as safety_cars,
           count_if(status = '6') as virtual_safety_cars,
           count_if(status = '5') as red_flags
    from {{ source('bronze', 'fastf1_track_status') }}
    where session = 'R'
    group by 1
),
rain as (
    select {{ race_id('season', 'round') }} as race_id,
           max(iff(lower(rainfall) = 'true', 1, 0)) = 1 as rain_measured
    from {{ source('bronze', 'fastf1_weather') }}
    where session = 'R'
    group by 1
)
select s.race_id, s.safety_cars, s.virtual_safety_cars, s.red_flags, r.rain_measured
from status s left join rain r using (race_id)
