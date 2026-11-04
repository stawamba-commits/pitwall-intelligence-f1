# Module: one Snowflake warehouse with PitWall's cost rules built in (course module).
terraform {
  required_providers {
    snowflake = { source = "snowflakedb/snowflake" }
  }
}

variable "name" { type = string }
variable "size" { type = string }
variable "comment" {
  type    = string
  default = ""
}

resource "snowflake_warehouse" "this" {
  name                = var.name
  warehouse_size      = var.size
  auto_suspend        = 60 # stop after 60 s idle: no credits burnt between runs
  auto_resume         = true
  initially_suspended = true
  comment             = var.comment
}

output "name" {
  value = snowflake_warehouse.this.name
}
