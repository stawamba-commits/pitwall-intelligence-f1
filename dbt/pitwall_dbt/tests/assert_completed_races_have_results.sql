-- COMPLETENESS: a race that ended more than 2 days before the run must have its results in gold
-- ("Sunday's results are there by Tuesday morning"). Seasons before the model's history are ignored.
select r.race_id, r.race_name, r.race_date
from {{ ref('dim_race') }} r
left join (select distinct race_id from {{ ref('fact_race_result') }}) f on f.race_id = r.race_id
where r.race_date < dateadd(day, -2, {{ run_date() }})
  and r.season >= {{ var('first_season') }}
  and f.race_id is null
