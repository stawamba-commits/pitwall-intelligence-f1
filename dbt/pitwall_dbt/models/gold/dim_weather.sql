-- One row per race: weather during the race (start -1 h to +3 h, UTC).
-- Past races use the archive, the next race the forecast. Rain measured at the track (FastF1) when we have it.
with window_hours as (
    select w.race_id, w.kind, w.temperature_c, w.precipitation_mm, w.precipitation_probability, w.wind_kmh
    from {{ ref('stg_weather_hourly') }} w
    join {{ ref('stg_races') }} r on r.race_id = w.race_id
    where w.hour_utc between timestampadd(hour, -1, timestamp_ntz_from_parts(r.race_date, coalesce(r.race_time_utc, '13:00'::time)))
                         and timestampadd(hour,  3, timestamp_ntz_from_parts(r.race_date, coalesce(r.race_time_utc, '13:00'::time)))
),
per_race as (
    select race_id,
           iff(count_if(kind = 'archive') > 0, 'archive', 'forecast') as weather_kind,
           avg(temperature_c)               as avg_temperature_c,
           sum(precipitation_mm)            as rain_mm,
           max(precipitation_probability)   as max_rain_probability,
           avg(wind_kmh)                    as avg_wind_kmh
    from window_hours
    where kind = 'archive' or race_id not in (select race_id from window_hours where kind = 'archive')
    group by race_id
)
select p.*,
       coalesce(e.rain_measured, p.rain_mm >= 0.5) as is_wet_race
from per_race p
left join {{ ref('stg_race_events') }} e using (race_id)
