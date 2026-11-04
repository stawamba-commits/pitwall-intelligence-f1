-- If more than 5 % of the results are rejected, a source is broken -> fail the build (course pattern).
select q.n as quarantined, s.n as kept
from (select count(*) n from {{ ref('results_quarantine') }}) q
cross join (select count(*) n from {{ ref('silver_results') }}) s
where q.n / nullif(q.n + s.n, 0) > 0.05
