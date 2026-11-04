-- One row per race. is_next_race = the first race on or after the run date (the one we predict).
select
    race_id, season, round, race_name, race_date, race_time_utc, quali_date, circuit_ref,
    race_date < {{ run_date() }}  as is_completed,
    race_id = (select min_by(race_id, race_date) from {{ ref('stg_races') }}
               where race_date >= {{ run_date() }}) as is_next_race
from {{ ref('stg_races') }}
