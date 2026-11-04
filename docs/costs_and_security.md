# Costs and security (C7)

## Security — proportionate to public sports data
- **Roles (Terraform):** `PITWALL_PIPELINE` writes in PITWALL; `PITWALL_ANALYST` (dashboard) only reads GOLD.
  Allowed / denied proof: `sql/01_access_check.sql` (gold readable, bronze not authorised, delete refused).
- **Secrets:** key-pair authentication; the private key is mounted read-only at run time, never in an image
  (`.dockerignore`) nor in Git (`.gitignore`); `.env` and `terraform.tfvars` are not committed.
- **Sensitive data:** the data is public, but drivers are people: the full date of birth stays in silver,
  gold only keeps the birth year (`dim_driver`). No customer data is stored by this pipeline.
- **Terraform state:** never committed; remote, versioned and locked backend in `terraform/backend.tf.example`.

## Prototype cost — estimate, to replace with the measured numbers
Measured numbers: last query of `sql/02_budget_monitor.sql` (credits per warehouse per day).

| Item | Assumption | Credits / month |
|---|---|---|
| Daily run (ingestion + dbt + model) on XSMALL (1 credit/hour) | ~6 min of warehouse per day × 30 | ≈ 3 |
| Race-weekend extra runs (manual) | 4 weekends × 3 runs × 6 min | ≈ 1.2 |
| Dashboard on its own XSMALL, 10-min cache | ~5 min per day | ≈ 2.5 |
| One-off backfill (Kaggle 1950-2024 + FastF1 2023-2025) | ~30 min once | 0.5 (once) |
| Storage | < 1 GB | ≈ 0 |
| **Total** | | **≈ 7 credits ≈ €20/month** at an assumed €3 per credit (depends on edition and region) |

**Projection ×10 customers:** ingestion and dbt do not change (same data); only the dashboard warehouse is
used more: ≈ 25 credits for the BI warehouse → ≈ 30 credits ≈ €90/month. Cost driver = readers, not data.

## Budget alert and shutdown
- Resource monitor `PITWALL_BUDGET`: 10 credits/month, e-mail at 50 % and 80 %, warehouses suspended at 100 %
  (`sql/02_budget_monitor.sql`).
- Warehouses suspend after 60 s idle (Terraform module).
- Shutdown / cleanup procedure: `sql/04_shutdown_cleanup.sql` (pause DAG, suspend, `terraform destroy`, drop monitor).
