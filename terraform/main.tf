# PitWall Analytics platform, declared as code.
# terraform plan = preview the changes      terraform apply = make them      terraform destroy = clean up

# ---------- storage: one database, one schema per layer ----------
resource "snowflake_database" "pitwall" {
  name    = "PITWALL"
  comment = "PitWall Analytics - managed by Terraform, do not change by hand"
}

resource "snowflake_schema" "layer" {
  for_each = toset(["BRONZE", "SILVER", "GOLD"])
  database = snowflake_database.pitwall.name
  name     = each.value
}

# ---------- compute: two XSMALL warehouses from the same module ----------
module "elt_warehouse" {
  source  = "./modules/warehouse"
  name    = "PITWALL_ELT_WH"
  size    = "XSMALL"
  comment = "Airflow: ingestion jobs, dbt, model"
}

module "bi_warehouse" {
  source  = "./modules/warehouse"
  name    = "PITWALL_BI_WH"
  size    = "XSMALL"
  comment = "Streamlit dashboard (separate warehouse: we can see what the dashboard costs)"
}

# ---------- access: least privilege ----------
# PIPELINE writes everywhere in PITWALL; ANALYST (the dashboard) can only READ GOLD.
resource "snowflake_account_role" "pipeline" {
  provider = snowflake.security
  name     = "PITWALL_PIPELINE"
  comment  = "Ingestion, dbt and model jobs"
}

resource "snowflake_account_role" "analyst" {
  provider = snowflake.security
  name     = "PITWALL_ANALYST"
  comment  = "Read-only on GOLD (dashboard, fans and media)"
}

resource "snowflake_grant_account_role" "pipeline_to_user" {
  provider  = snowflake.security
  role_name = snowflake_account_role.pipeline.name
  user_name = var.user
}

resource "snowflake_grant_account_role" "roles_to_sysadmin" {
  for_each         = toset([snowflake_account_role.pipeline.name, snowflake_account_role.analyst.name])
  provider         = snowflake.security
  role_name        = each.value
  parent_role_name = "SYSADMIN"
}

resource "snowflake_grant_privileges_to_account_role" "pipeline_database" {
  provider          = snowflake.security
  account_role_name = snowflake_account_role.pipeline.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.pitwall.name
  }
}

# The pipeline creates its own tables (it then owns them); write_pandas also needs a temporary stage.
resource "snowflake_grant_privileges_to_account_role" "pipeline_schemas" {
  for_each          = snowflake_schema.layer
  provider          = snowflake.security
  account_role_name = snowflake_account_role.pipeline.name
  privileges        = ["USAGE", "CREATE TABLE", "CREATE VIEW", "CREATE STAGE", "CREATE FILE FORMAT"]
  on_schema {
    schema_name = each.value.fully_qualified_name
  }
}

resource "snowflake_grant_privileges_to_account_role" "pipeline_warehouse" {
  provider          = snowflake.security
  account_role_name = snowflake_account_role.pipeline.name
  privileges        = ["USAGE", "OPERATE"]
  on_account_object {
    object_type = "WAREHOUSE"
    object_name = module.elt_warehouse.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "analyst_warehouse" {
  provider          = snowflake.security
  account_role_name = snowflake_account_role.analyst.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "WAREHOUSE"
    object_name = module.bi_warehouse.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "analyst_database" {
  provider          = snowflake.security
  account_role_name = snowflake_account_role.analyst.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.pitwall.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "analyst_gold_schema" {
  provider          = snowflake.security
  account_role_name = snowflake_account_role.analyst.name
  privileges        = ["USAGE"]
  on_schema {
    schema_name = snowflake_schema.layer["GOLD"].fully_qualified_name
  }
}

resource "snowflake_grant_privileges_to_account_role" "analyst_gold_tables" {
  provider          = snowflake.security
  account_role_name = snowflake_account_role.analyst.name
  privileges        = ["SELECT"]
  on_schema_object {
    future {
      object_type_plural = "TABLES"
      in_schema          = snowflake_schema.layer["GOLD"].fully_qualified_name
    }
  }
}
