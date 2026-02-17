output "state_bucket_name" {
  value       = module.tf_state.bucket_id
  description = "Name of the S3 bucket used for Terraform remote state."
}
