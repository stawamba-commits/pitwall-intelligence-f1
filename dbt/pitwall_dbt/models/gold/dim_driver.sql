-- One row per driver. Personal data minimised: birth YEAR only, the full date stays in silver.
select
    driver_ref,
    max_by(driver_code, season * 100 + round) as driver_code,
    max_by(driver_name, season * 100 + round) as driver_name,
    year(min(driver_dob))                     as birth_year
from {{ ref('silver_results') }}
group by driver_ref
