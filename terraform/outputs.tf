output "database" { value = snowflake_database.pitwall.name }
output "elt_warehouse" { value = module.elt_warehouse.name }
output "bi_warehouse" { value = module.bi_warehouse.name }
output "analyst_role" { value = snowflake_account_role.analyst.name }
