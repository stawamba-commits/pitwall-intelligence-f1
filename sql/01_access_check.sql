-- C7 · Proportionate access, ALLOWED / DENIED verification. Run in a Snowsight worksheet.
-- The analyst role (used by the dashboard) can read GOLD and nothing else.
-- (Grant the role to yourself first, once:  USE ROLE SECURITYADMIN; GRANT ROLE PITWALL_ANALYST TO USER <you>;)

USE ROLE PITWALL_ANALYST;
USE WAREHOUSE PITWALL_BI_WH;

-- ALLOWED: expected result = rows
SELECT race_id, driver_ref, predicted_rank, p_podium
FROM PITWALL.GOLD.UC1_PODIUM_PREDICTIONS
ORDER BY race_id DESC, predicted_rank
LIMIT 5;

-- DENIED: expected error = "Schema 'PITWALL.BRONZE' does not exist or not authorized."
SELECT COUNT(*) FROM PITWALL.BRONZE.JOLPICA_RAW;

-- DENIED: the analyst cannot write either. Expected error = "Insufficient privileges"
DELETE FROM PITWALL.GOLD.UC1_PODIUM_PREDICTIONS;
