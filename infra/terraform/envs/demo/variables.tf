variable "aws_region" {
  type        = string
  description = "The AWS region where resources will be deployed."
}

variable "environment" {
  type        = string
  description = "The environment name (e.g., demo, prod)."
}

variable "data_bucket_name" {
  type        = string
  description = "The name of the S3 bucket where ENTSO-E data will be stored."
}