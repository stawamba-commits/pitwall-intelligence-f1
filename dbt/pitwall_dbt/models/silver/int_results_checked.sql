-- Every race result from Jolpica (A) and Kaggle (B), typed, with the list of problems found on the row.
-- silver_results keeps the good rows, results_quarantine the others: nothing is lost (course pattern).
{{ config(materialized='view') }}
with jolpica as (
    select
        j.season::int as season, j.round::int as round,
        x.value:Driver:driverId::string              as driver_ref,
        x.value:Driver:code::string                  as driver_code,
        x.value:Driver:givenName::string || ' ' || x.value:Driver:familyName::string as driver_name,
        try_to_date(x.value:Driver:dateOfBirth::string) as driver_dob,
        x.value:Constructor:constructorId::string    as constructor_ref,
        x.value:Constructor:name::string             as constructor_name,
        try_to_number(x.value:grid::string)          as grid,
        try_to_number(x.value:position::string)      as finish_order,
        try_to_double(x.value:points::string)        as points,
        try_to_number(x.value:laps::string)          as laps,
        x.value:status::string                       as status,
        try_to_number(x.value:Time:millis::string)   as race_time_ms,
        'jolpica' as source, 1 as priority, j._loaded_at
    from {{ source('bronze', 'jolpica_raw') }} j,
         lateral flatten(input => j.payload:MRData:RaceTable:Races) r,
         lateral flatten(input => r.value:Results) x
    where j.endpoint = 'results'
),
kaggle as (
    select
        try_to_number(ra.year), try_to_number(ra.round),
        d.driverref, {{ na('d.code') }}, d.forename || ' ' || d.surname, try_to_date({{ na('d.dob') }}),
        c.constructorref, c.name,
        try_to_number({{ na('r.grid') }}), try_to_number({{ na('r.positionorder') }}),
        try_to_double({{ na('r.points') }}), try_to_number({{ na('r.laps') }}),
        s.status, try_to_number({{ na('r.milliseconds') }}),
        'kaggle', 2, r._loaded_at
    from {{ source('bronze', 'kaggle_results') }} r
    left join {{ source('bronze', 'kaggle_races') }} ra on ra.raceid = r.raceid
    left join {{ source('bronze', 'kaggle_drivers') }} d on d.driverid = r.driverid
    left join {{ source('bronze', 'kaggle_constructors') }} c on c.constructorid = r.constructorid
    left join {{ source('bronze', 'kaggle_status') }} s on s.statusid = r.statusid
),
deduped as (
    -- Which version wins when the same result exists twice? Jolpica first (corrected after penalties),
    -- then the latest load. Deterministic: two runs on the same data give the same result.
    select * from (select * from jolpica union all select * from kaggle)
    qualify row_number() over (partition by season, round, driver_ref
                               order by priority, _loaded_at desc, constructor_ref) = 1
)
select
    {{ race_id('d.season', 'd.round') }} as race_id,
    d.*,
    array_construct_compact(
        iff(d.driver_ref is null, 'missing driver', null),
        iff(rc.race_id is null, 'race not in the calendar', null),
        iff(d.grid is null or d.grid not between 0 and 40, 'grid missing or out of range', null),
        iff(d.finish_order is null or d.finish_order not between 1 and 40, 'finish position out of range', null)
    ) as problems
from deduped d
left join {{ ref('stg_races') }} rc on rc.race_id = {{ race_id('d.season', 'd.round') }}
