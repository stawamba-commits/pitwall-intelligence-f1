-- Rows that would make a business number wrong: kept aside WITH their reason, never silently dropped.
select race_id, season, round, driver_ref, constructor_ref, grid, finish_order, status, source, problems
from {{ ref('int_results_checked') }}
where array_size(problems) > 0
