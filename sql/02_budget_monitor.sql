-- C7 · Budget alert. Manual step (needs ACCOUNTADMIN, which our Terraform user does not use).
-- 10 credits per month is far above what the prototype needs (see docs/costs_and_security.md):
-- at 50 % and 80 % the account admins get an e-mail, at 100 % the warehouses are SUSPENDED.
USE ROLE ACCOUNTADMIN;

CREATE OR REPLACE RESOURCE MONITOR PITWALL_BUDGET
  WITH CREDIT_QUOTA = 10
  FREQUENCY = MONTHLY
  START_TIMESTAMP = IMMEDIATELY
  TRIGGERS ON 50 PERCENT DO NOTIFY
           ON 80 PERCENT DO NOTIFY
           ON 100 PERCENT DO SUSPEND;

ALTER WAREHOUSE PITWALL_ELT_WH SET RESOURCE_MONITOR = PITWALL_BUDGET;
ALTER WAREHOUSE PITWALL_BI_WH  SET RESOURCE_MONITOR = PITWALL_BUDGET;

-- What did we really spend? (credits per warehouse and per day, last 30 days)
SELECT warehouse_name, TO_DATE(start_time) AS day, ROUND(SUM(credits_used), 3) AS credits
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE warehouse_name LIKE 'PITWALL%' AND start_time >= DATEADD(day, -30, CURRENT_TIMESTAMP())
GROUP BY 1, 2 ORDER BY 2 DESC, 1;
