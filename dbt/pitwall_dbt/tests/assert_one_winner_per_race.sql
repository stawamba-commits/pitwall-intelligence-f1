-- BUSINESS RULE: every completed race has exactly one winner (finish_order = 1).
-- Loading the same race twice WITHOUT the MERGE, or a broken source, makes this test fail
-- and `dbt build` then skips everything downstream: the bad data never reaches the dashboard.
select f.race_id, count_if(f.finish_order = 1) as winners
from {{ ref('fact_race_result') }} f
group by f.race_id
having count_if(f.finish_order = 1) != 1
