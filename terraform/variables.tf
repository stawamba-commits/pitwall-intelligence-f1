variable "organization_name" {
  description = "First part of your account identifier (before the dash), e.g. ABCDEFG"
  type        = string
}

variable "account_name" {
  description = "Second part of your account identifier (after the dash), e.g. XY12345"
  type        = string
}

variable "user" {
  description = "Snowflake user that runs the pipeline (the one with the RSA key)"
  type        = string
}

variable "private_key_path" {
  description = "Path to rsa_key.p8. Never commit the key itself."
  type        = string
  default     = "../../keys/rsa_key.p8"
}
