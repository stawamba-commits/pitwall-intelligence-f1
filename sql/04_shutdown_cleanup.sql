-- C7 · Shutdown / cleanup procedure (after the defence).
-- 1. Stop the schedule: in Airflow, pause the DAG pitwall_daily (toggle), then `docker compose down`.
-- 2. Stop compute now (they would auto-suspend after 60 s anyway):
USE ROLE SYSADMIN;
ALTER WAREHOUSE IF EXISTS PITWALL_ELT_WH SUSPEND;
ALTER WAREHOUSE IF EXISTS PITWALL_BI_WH SUSPEND;
-- 3. Delete everything Terraform created (database, schemas, warehouses, roles, grants):
--      cd terraform && terraform plan -destroy && terraform destroy
-- 4. Manual objects, not in Terraform:
USE ROLE ACCOUNTADMIN;
DROP RESOURCE MONITOR IF EXISTS PITWALL_BUDGET;
-- 5. Revoke the RSA public key of the pipeline user if the project stops:
--      ALTER USER <you> UNSET RSA_PUBLIC_KEY;
