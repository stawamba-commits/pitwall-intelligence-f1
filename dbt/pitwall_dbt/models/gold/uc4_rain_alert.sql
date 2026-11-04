-- UC4 · Rain alert for the next race: forecast rain probability per session window, plus how often
-- this circuit had a wet race in the past. Fantasy players change their picks before the deadline.
with next_race as (
    select * from {{ ref('dim_race') }} where is_next_race
),
sessions as (       -- simple windows (UTC): qualifying on the day before the race, same hour
    select race_id, 'Qualifying' as session, timestampadd(day, -1, timestamp_ntz_from_parts(race_date, coalesce(race_time_utc, '13:00'::time))) as starts_at from next_race
    union all
    select race_id, 'Race', timestamp_ntz_from_parts(race_date, coalesce(race_time_utc, '13:00'::time)) from next_race
),
forecast as (
    select s.race_id, s.session, s.starts_at,
           max(w.precipitation_probability) as max_rain_probability,
           sum(w.precipitation_mm)          as rain_mm
    from sessions s
    join {{ ref('stg_weather_hourly') }} w
      on w.race_id = s.race_id and w.kind = 'forecast'
     and w.hour_utc between timestampadd(hour, -1, s.starts_at) and timestampadd(hour, 3, s.starts_at)
    group by 1, 2, 3
),
history as (
    select r.circuit_ref, count(*) as past_races, count_if(w.is_wet_race) as wet_races
    from {{ ref('dim_race') }} r join {{ ref('dim_weather') }} w on w.race_id = r.race_id
    where r.is_completed
    group by 1
)
select
    n.race_id, n.race_name, f.session, f.starts_at, f.max_rain_probability, f.rain_mm,
    case when f.max_rain_probability >= 60 then 'HIGH'
         when f.max_rain_probability >= 30 then 'MEDIUM'
         else 'LOW' end                                         as alert_level,
    h.wet_races, h.past_races
from next_race n
left join forecast f on f.race_id = n.race_id
left join history h on h.circuit_ref = n.circuit_ref
