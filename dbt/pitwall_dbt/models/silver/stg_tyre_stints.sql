-- FastF1 (D) tyre stints of each race: one row per race x driver x stint.
select
    {{ race_id('season', 'round') }}  as race_id,
    driver_code,
    try_to_double({{ na('stint') }})::int as stint,
    upper({{ na('compound') }})       as compound,
    try_to_number({{ na('laps') }})   as laps
from {{ source('bronze', 'fastf1_stints') }}
where upper({{ na('compound') }}) in ('SOFT', 'MEDIUM', 'HARD', 'INTERMEDIATE', 'WET')
