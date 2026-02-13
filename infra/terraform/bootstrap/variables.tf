variable "aws_region" {
  type        = string
  description = "AWS region to create the Terraform state bucket in."
}

variable "state_bucket_name" {
  type        = string
  description = "Globally-unique S3 bucket name for Terraform remote state."
}