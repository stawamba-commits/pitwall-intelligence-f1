-- One row per team (constructor), with its latest name.
select constructor_ref, max_by(constructor_name, season * 100 + round) as constructor_name
from {{ ref('silver_results') }}
group by constructor_ref
