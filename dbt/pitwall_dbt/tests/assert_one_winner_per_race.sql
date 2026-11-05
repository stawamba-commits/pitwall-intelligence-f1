-- BUSINESS RULE: every completed race has exactly one winner (finish_order = 1).
-- Loading the same race twice WITHOUT the MERGE, or a broken source, makes this test fail
-- and `dbt build` then skips everything downstream: the bad data never reaches the dashboard.
-- Scope: from 1958. Before that, two drivers could share one car and BOTH were credited with the win
-- (e.g. 1956 Argentine GP, Fangio + Musso): a real historical rule, not a data error. Found by this test.
select f.race_id, count_if(f.finish_order = 1) as winners
from {{ ref('fact_race_result') }} f
where try_to_number(left(f.race_id, 4)) >= 1958
group by f.race_id
having count_if(f.finish_order = 1) != 1
