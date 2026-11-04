-- Open-Meteo (C): one row per race x kind (archive / forecast) x hour, timestamps in UTC.
select
    {{ race_id('w.season', 'w.round') }}                               as race_id,
    w.kind,
    t.value::timestamp_ntz                                              as hour_utc,
    w.payload:hourly:temperature_2m[t.index]::float                     as temperature_c,
    w.payload:hourly:precipitation[t.index]::float                      as precipitation_mm,
    w.payload:hourly:precipitation_probability[t.index]::float          as precipitation_probability,
    w.payload:hourly:wind_speed_10m[t.index]::float                     as wind_kmh,
    w._loaded_at
from {{ source('bronze', 'weather_raw') }} w,
     lateral flatten(input => w.payload:hourly:time) t
