-- C6 · Incident drills, run in a Snowsight worksheet (role PITWALL_PIPELINE). See docs/incidents.md.

USE ROLE PITWALL_PIPELINE;
USE WAREHOUSE PITWALL_ELT_WH;
USE SCHEMA PITWALL.BRONZE;

-- =====================================================================================
-- DRILL B · Replay without double counting
-- 1. Note the numbers BEFORE
SELECT (SELECT COUNT(*) FROM BRONZE.JOLPICA_RAW)                                   AS bronze_rows,
       (SELECT COUNT(*) FROM GOLD.FACT_RACE_RESULT)                                AS fact_rows,
       (SELECT SUM(points) FROM GOLD.FACT_RACE_RESULT WHERE race_id LIKE '2026-%') AS points_2026;
-- 2. Trigger the same Airflow run again (Clear the task), or run twice:
--      docker run ... pitwall-jobs:1.0.0 python ingest_jolpica.py --run-date 2026-11-09
--    then dbt build.
-- 3. Run the query of step 1 again: SAME numbers (MERGE on ENDPOINT+SEASON+ROUND, dedup in silver).

-- =====================================================================================
-- DRILL C · A broken source appends a second winner for a finished race (no MERGE)
INSERT INTO BRONZE.JOLPICA_RAW (ENDPOINT, SEASON, ROUND, PAYLOAD, _SOURCE, _LOADED_AT, _RUN_ID)
SELECT 'results', '2026', '20', PARSE_JSON('{"MRData":{"RaceTable":{"Races":[{"season":"2026","round":"20",
  "Results":[{"position":"1","positionText":"1","points":"25","grid":"5","laps":"71","status":"Finished",
  "Driver":{"driverId":"ghost_driver","code":"GHO","givenName":"Ghost","familyName":"Driver"},
  "Constructor":{"constructorId":"ghost_team","name":"Ghost Team"}}]}]}}}'),
  'incident-drill', CURRENT_TIMESTAMP(), 'drill-c';
-- Now run `dbt build`: assert_one_winner_per_race FAILS on race 2026-20 and every model downstream
-- of fact_race_result is SKIPPED -> the dashboard keeps yesterday's correct numbers.

-- Recovery: remove the bad rows, rebuild, the test passes again.
DELETE FROM BRONZE.JOLPICA_RAW WHERE _SOURCE = 'incident-drill';
