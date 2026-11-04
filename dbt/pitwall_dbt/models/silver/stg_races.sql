-- One row per race (season-round), from the Jolpica calendar (A) and the Kaggle history (B).
-- Which version wins? Jolpica (the live source, it gets corrections), then the latest load.
with jolpica as (
    select
        r.value:season::int                         as season,
        r.value:round::int                          as round,
        r.value:raceName::string                    as race_name,
        r.value:Circuit:circuitId::string           as circuit_ref,
        r.value:Circuit:circuitName::string         as circuit_name,
        r.value:Circuit:Location:country::string    as country,
        r.value:Circuit:Location:lat::float         as lat,
        r.value:Circuit:Location:long::float        as lon,
        r.value:date::date                          as race_date,
        try_to_time(replace(r.value:time::string, 'Z', ''))              as race_time_utc,
        r.value:Qualifying:date::date               as quali_date,
        1 as priority, j._loaded_at
    from {{ source('bronze', 'jolpica_raw') }} j,
         lateral flatten(input => j.payload:MRData:RaceTable:Races) r
    where j.endpoint = 'schedule'
),
kaggle as (
    select
        try_to_number(r.year), try_to_number(r.round), r.name, c.circuitref, c.name, c.country,
        try_to_double(c.lat), try_to_double(c.lng),
        try_to_date({{ na('r.date') }}), try_to_time({{ na('r.time') }}),
        try_to_date({{ na('r.quali_date') }}),
        2 as priority, r._loaded_at
    from {{ source('bronze', 'kaggle_races') }} r
    left join {{ source('bronze', 'kaggle_circuits') }} c on c.circuitid = r.circuitid
),
all_races as (
    select * from jolpica
    union all
    select * from kaggle
)
select
    {{ race_id('season', 'round') }} as race_id,
    season, round, race_name, circuit_ref, circuit_name, country, lat, lon,
    race_date, race_time_utc, quali_date
from all_races
where season is not null and round is not null
qualify row_number() over (partition by season, round order by priority, _loaded_at desc) = 1
