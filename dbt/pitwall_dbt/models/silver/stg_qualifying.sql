-- Qualifying: one row per race x driver, best lap of Q1/Q2/Q3 in seconds.
with jolpica as (
    select
        j.season::int as season, j.round::int as round,
        x.value:Driver:driverId::string           as driver_ref,
        x.value:Constructor:constructorId::string as constructor_ref,
        try_to_number(x.value:position::string)   as quali_position,
        {{ lap_seconds("x.value:Q1::string") }}   as q1_s,
        {{ lap_seconds("x.value:Q2::string") }}   as q2_s,
        {{ lap_seconds("x.value:Q3::string") }}   as q3_s,
        1 as priority, j._loaded_at
    from {{ source('bronze', 'jolpica_raw') }} j,
         lateral flatten(input => j.payload:MRData:RaceTable:Races) r,
         lateral flatten(input => r.value:QualifyingResults) x
    where j.endpoint = 'qualifying'
),
kaggle as (
    select
        try_to_number(ra.year), try_to_number(ra.round), d.driverref, c.constructorref,
        try_to_number({{ na('q.position') }}),
        {{ lap_seconds('q.q1') }}, {{ lap_seconds('q.q2') }}, {{ lap_seconds('q.q3') }},
        2, q._loaded_at
    from {{ source('bronze', 'kaggle_qualifying') }} q
    left join {{ source('bronze', 'kaggle_races') }} ra on ra.raceid = q.raceid
    left join {{ source('bronze', 'kaggle_drivers') }} d on d.driverid = q.driverid
    left join {{ source('bronze', 'kaggle_constructors') }} c on c.constructorid = q.constructorid
)
select
    {{ race_id('season', 'round') }} as race_id, season, round, driver_ref, constructor_ref, quali_position,
    q1_s, q2_s, q3_s,
    nullif(least(coalesce(q1_s, 999), coalesce(q2_s, 999), coalesce(q3_s, 999)), 999) as best_quali_s
from (select * from jolpica union all select * from kaggle)
where driver_ref is not null
qualify row_number() over (partition by season, round, driver_ref order by priority, _loaded_at desc) = 1
