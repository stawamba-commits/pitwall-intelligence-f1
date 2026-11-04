-- Pit stops: one row per race x driver x stop number (Jolpica first, then Kaggle history).
with jolpica as (
    select
        j.season::int as season, j.round::int as round,
        x.value:driverId::string               as driver_ref,
        try_to_number(x.value:stop::string)    as stop,
        try_to_number(x.value:lap::string)     as lap,
        {{ lap_seconds("x.value:duration::string") }} as duration_s,
        1 as priority, j._loaded_at
    from {{ source('bronze', 'jolpica_raw') }} j,
         lateral flatten(input => j.payload:MRData:RaceTable:Races) r,
         lateral flatten(input => r.value:PitStops) x
    where j.endpoint = 'pitstops'
),
kaggle as (
    select try_to_number(ra.year), try_to_number(ra.round), d.driverref,
           try_to_number(p.stop), try_to_number(p.lap), {{ lap_seconds('p.duration') }}, 2, p._loaded_at
    from {{ source('bronze', 'kaggle_pit_stops') }} p
    left join {{ source('bronze', 'kaggle_races') }} ra on ra.raceid = p.raceid
    left join {{ source('bronze', 'kaggle_drivers') }} d on d.driverid = p.driverid
)
select {{ race_id('season', 'round') }} as race_id, season, round, driver_ref, stop, lap, duration_s
from (select * from jolpica union all select * from kaggle)
where driver_ref is not null
qualify row_number() over (partition by season, round, driver_ref, stop order by priority, _loaded_at desc) = 1
